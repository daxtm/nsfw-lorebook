#!/usr/bin/env bash
# One-command setup + launcher for llama.cpp across two GPUs of different
# vendors on one machine, using llama.cpp's RPC backend:
#
#   - ggml-rpc-server (Vulkan build) -> AMD RX 9070
#   - ggml-rpc-server (CUDA build)   -> NVIDIA RTX 5070 Ti
#   - llama-server (CUDA build, no local GPU) coordinates both and serves
#     an OpenAI-compatible endpoint on port 8081 (all interfaces) for SillyTavern.
#
# Usage:
#   tools/llamacpp-rpc-setup.sh                    # download/update binaries only
#   tools/llamacpp-rpc-setup.sh --run MODEL [CTX]  # set up if needed, then launch
#   tools/llamacpp-rpc-setup.sh --dry-run          # show the plan, download nothing
#
# MODEL is a local .gguf path or an http(s) URL (downloaded into models/).
# CTX defaults to 16384. Ctrl-C stops llama-server and both RPC servers.
#
# Overrides (environment):
#   LLAMACPP_DIR   install dir                      (default: ~/llama-rpc)
#   CUDA_LABEL     Ubuntu CUDA build label          (default: 12.8; try 13.5)
#   VK_DEVICE      Vulkan index for the AMD card    (default: auto-detect)
#   CUDA_DEVICE    CUDA index for the NVIDIA card   (default: 0)
#   VK_PORT, CUDA_PORT, PORT                        (default: 50052, 50053, 8081)
#   CTX            default context size             (default: 16384)
#   KV_TYPE        KV cache type                    (default: q8_0; q4_0 = smaller, lossier)
#   HOST           bind address for llama-server    (default: 0.0.0.0 = whole LAN)
#   API_KEY        optional bearer token            (default: none)
#   FORCE=1        re-download even if already installed
set -euo pipefail

REPO="ggml-org/llama.cpp"
DIR="${LLAMACPP_DIR:-$HOME/llama-rpc}"
CUDA_LABEL="${CUDA_LABEL:-12.8}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"
VK_PORT="${VK_PORT:-50052}"
CUDA_PORT="${CUDA_PORT:-50053}"
PORT="${PORT:-8081}"
DEFAULT_CTX="${CTX:-16384}"
KV_TYPE="${KV_TYPE:-q8_0}"
HOST="${HOST:-0.0.0.0}"
API_KEY="${API_KEY:-}"
PROBE_PORT=50098

MODE="setup"
MODEL=""
CTX_ARG=""

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() {
	printf 'error: %s\n' "$*" >&2
	exit 1
}
need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

usage() {
	# Print the whole leading comment block, however long it grows: stop at the
	# first non-comment line instead of a hardcoded line range.
	awk 'NR==1 || /^#!/ {next} !/^#/ {exit} {sub(/^# ?/, ""); print}' "$0"
	exit 0
}

TMP_FILES=()
PIDS=()
cleanup() {
	trap - EXIT INT TERM
	if ((${#PIDS[@]})); then
		for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done
	fi
	if ((${#TMP_FILES[@]})); then
		for f in "${TMP_FILES[@]}"; do rm -f "$f"; done
	fi
}
trap cleanup EXIT INT TERM

port_busy() {
	python3 - "$1" <<'PY'
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.3)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
}

wait_port() {
	local port="$1"
	for _ in $(seq 1 60); do
		port_busy "$port" && return 0
		sleep 0.2
	done
	return 1
}

# Locate a binary by trying several names in a directory tree.
find_bin() {
	local dir="$1" name found
	shift
	for name in "$@"; do
		found="$(find "$dir" -maxdepth 3 -type f -name "$name" 2>/dev/null | head -n1 || true)"
		if [[ -n "$found" ]]; then
			printf '%s' "$found"
			return 0
		fi
	done
	return 1
}

fetch_extract() {
	local url="$1" dest="$2" tmp
	tmp="$(mktemp --suffix=.tar.gz)"
	TMP_FILES+=("$tmp")
	say "Downloading $(basename "$url")"
	curl -fL --retry 3 --retry-delay 2 -o "$tmp" "$url"
	mkdir -p "$dest"
	tar -xzf "$tmp" -C "$dest" --strip-components=1
	rm -f "$tmp"
}

parse_args() {
	case "${1:-}" in
	--run)
		MODE="run"
		MODEL="${2:-}"
		CTX_ARG="${3:-}"
		[[ -n "$MODEL" ]] || die "--run needs a model path (or URL)"
		;;
	--dry-run) MODE="dry" ;;
	-h | --help) usage ;;
	"") ;;
	*) die "unknown argument: $1 (see --help)" ;;
	esac
}

resolve_release() {
	local json
	json="$(mktemp)"
	TMP_FILES+=("$json")
	say "Resolving latest llama.cpp release (CUDA $CUDA_LABEL + Vulkan)"
	curl -fsSL -H 'User-Agent: llamacpp-rpc-setup' \
		"https://api.github.com/repos/$REPO/releases?per_page=15" -o "$json"

	RESOLVED=()
	mapfile -t RESOLVED < <(
		python3 - "$json" "$CUDA_LABEL" <<'PY'
import json, sys
path, label = sys.argv[1], sys.argv[2]
data = json.load(open(path))
rels = data if isinstance(data, list) else [data]
for rel in rels:
    assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
    vk = next((n for n in assets if n.startswith("llama-") and
               n.endswith("bin-ubuntu-vulkan-x64.tar.gz")), None)
    cu = next((n for n in assets if n.startswith("llama-") and
               n.endswith(f"bin-ubuntu-cuda-{label}-x64.tar.gz")), None)
    rt = next((n for n in assets if n.startswith("cudart-llama-") and
               n.endswith(f"cuda-{label}-x64.tar.gz")), None)
    if vk and cu and rt:
        print(rel["tag_name"])
        print(assets[vk])
        print(assets[cu])
        print(assets[rt])
        break
else:
    sys.exit(f"no release with ubuntu vulkan/cuda {label}/cudart assets found")
PY
	)
	((${#RESOLVED[@]} == 4)) || die "could not resolve release assets (try CUDA_LABEL=12.8 or 13.5)"
	TAG="${RESOLVED[0]}"
	VK_URL="${RESOLVED[1]}"
	CUDA_URL="${RESOLVED[2]}"
	CUDART_URL="${RESOLVED[3]}"
}

# Locate the binaries if (and only if) they are all present, without dying.
# Sets VK_RPC/CUDA_RPC/SERVER and succeeds, or sets nothing and fails.
try_locate_bins() {
	local vk cu srv
	vk="$(find_bin "$DIR/vulkan" ggml-rpc-server rpc-server)" || return 1
	cu="$(find_bin "$DIR/cuda" ggml-rpc-server rpc-server)" || return 1
	srv="$(find_bin "$DIR/cuda" llama-server)" || return 1
	[[ -x "$vk" && -x "$cu" && -x "$srv" ]] || return 1
	VK_RPC="$vk"
	CUDA_RPC="$cu"
	SERVER="$srv"
}

# Detect an existing install: sets TAG and the binary paths in the CURRENT
# shell and succeeds, or returns non-zero. Never touches the network.
# Deliberately not used inside $(...) — the assignments would be lost in the
# subshell and later stages would see unbound VK_RPC/CUDA_RPC/SERVER.
installed_tag() {
	local marker="$DIR/state" state
	[[ "${FORCE:-0}" == "1" ]] && return 1
	[[ -f "$marker" ]] || return 1
	state="$(cat "$marker" 2>/dev/null || true)"
	[[ -n "$state" && "$state" == *" cuda-$CUDA_LABEL" ]] || return 1
	try_locate_bins || return 1
	TAG="${state% cuda-$CUDA_LABEL}"
}

install_bins() {
	local marker="$DIR/state" want
	want="$TAG cuda-$CUDA_LABEL"
	# try_locate_bins, not -x on unset vars: SERVER/VK_RPC/CUDA_RPC are only
	# populated here or by locate_bins, so testing them directly was always false.
	if try_locate_bins && [[ "$(cat "$marker" 2>/dev/null || true)" == "$want" ]]; then
		say "Binaries already installed ($TAG), skipping download (FORCE=1 to redo)"
		return 0
	fi

	mkdir -p "$DIR/logs" "$DIR/models"
	fetch_extract "$VK_URL" "$DIR/vulkan"
	fetch_extract "$CUDA_URL" "$DIR/cuda"
	fetch_extract "$CUDART_URL" "$DIR/cuda"

	VK_RPC="$(find_bin "$DIR/vulkan" ggml-rpc-server rpc-server)" || die "no ggml-rpc-server found in Vulkan package"
	CUDA_RPC="$(find_bin "$DIR/cuda" ggml-rpc-server rpc-server)" || die "no ggml-rpc-server found in CUDA package"
	SERVER="$(find_bin "$DIR/cuda" llama-server)" || die "no llama-server found in CUDA package"
	chmod +x "$VK_RPC" "$CUDA_RPC" "$SERVER"
	printf '%s\n' "$want" >"$marker"
	say "Installed $TAG into $DIR"
}

locate_bins() {
	VK_RPC="$(find_bin "$DIR/vulkan" ggml-rpc-server rpc-server)" || die "Vulkan binaries missing; run without --run first"
	CUDA_RPC="$(find_bin "$DIR/cuda" ggml-rpc-server rpc-server)" || die "CUDA binaries missing; run without --run first"
	SERVER="$(find_bin "$DIR/cuda" llama-server)" || die "llama-server missing; run without --run first"
}

detect_vk_device() {
	if [[ -n "${VK_DEVICE:-}" ]]; then
		printf '%s' "$VK_DEVICE"
		return 0
	fi
	local out line idx
	out="$(timeout 8 env LD_LIBRARY_PATH="$DIR/vulkan" "$VK_RPC" \
		-H 127.0.0.1 -p "$PROBE_PORT" 2>&1 || true)"
	line="$(printf '%s\n' "$out" | grep -Ei '(radeon|amd|9070|gfx[0-9])' | grep -Ei '(vulkan|vk)[0-9]+' | head -n1 || true)"
	idx="$(printf '%s' "$line" | grep -oiE '(vulkan|vk)[0-9]+' | grep -oE '[0-9]+' | head -n1 || true)"
	if [[ -z "$idx" ]]; then
		printf '%s\n' "$out" | sed -n '/Devices:/,$p' >&2 || true
		die "could not identify the AMD Vulkan device; set VK_DEVICE=<n> (index from the list above)"
	fi
	printf '%s' "$idx"
}

start_rpc() {
	local name="$1" bin="$2" log="$3" device="$4" port="$5"
	say "Starting $name RPC server on 127.0.0.1:$port (device $device)"
	(LD_LIBRARY_PATH="$(dirname "$bin")" exec "$bin" \
		-H 127.0.0.1 -p "$port" --device "$device") >"$log" 2>&1 &
	PIDS+=("$!")
}

run_server() {
	local model="$1" ctx="$2" vk_dev="$3"

	port_busy "$VK_PORT" && die "port $VK_PORT is already in use (another setup running?)"
	port_busy "$CUDA_PORT" && die "port $CUDA_PORT is already in use (another setup running?)"
	port_busy "$PORT" && die "port $PORT is already in use (SillyTavern backend already running?)"

	mkdir -p "$DIR/logs"
	start_rpc "Vulkan/AMD" "$VK_RPC" "$DIR/logs/vulkan-rpc.log" "Vulkan$vk_dev" "$VK_PORT"
	start_rpc "CUDA/NVIDIA" "$CUDA_RPC" "$DIR/logs/cuda-rpc.log" "CUDA$CUDA_DEVICE" "$CUDA_PORT"

	if ! wait_port "$VK_PORT"; then
		tail -n 20 "$DIR/logs/vulkan-rpc.log" >&2 || true
		die "Vulkan RPC server did not start (log: $DIR/logs/vulkan-rpc.log)"
	fi
	if ! wait_port "$CUDA_PORT"; then
		tail -n 20 "$DIR/logs/cuda-rpc.log" >&2 || true
		die "CUDA RPC server did not start (log: $DIR/logs/cuda-rpc.log)"
	fi

	case "$model" in
	http://* | https://*)
		local fname="$DIR/models/${model##*/}"
		fname="${fname%%\?*}"
		if [[ ! -f "$fname" ]]; then
			say "Downloading model to $fname"
			curl -fL --retry 3 -o "$fname.part" "$model"
			mv "$fname.part" "$fname"
		fi
		model="$fname"
		;;
	esac
	[[ -f "$model" ]] || die "model file not found: $model"

	say "Starting llama-server on port $PORT (bind $HOST, ctx $ctx, model $(basename "$model"))"
	say "SillyTavern: URL http://127.0.0.1:$PORT locally, or http://<this-pc-lan-ip>:$PORT from another PC"
	if [[ -n "$API_KEY" ]]; then
		say "API key required: send 'Authorization: Bearer <key>'"
	fi
	printf 'Ctrl-C stops the server and both RPC workers.\n\n'

	# No local GPU for the coordinator: both cards are owned by the RPC servers.
	# No explicit -ngl: the default --fit auto-places layers and spills the rest
	# to CPU instead of hard-failing when VRAM is tight.
	local extra=()
	[[ -n "$API_KEY" ]] && extra+=(--api-key "$API_KEY")
	CUDA_VISIBLE_DEVICES='' LD_LIBRARY_PATH="$DIR/cuda" \
		"$SERVER" -m "$model" \
		--rpc "127.0.0.1:$VK_PORT,127.0.0.1:$CUDA_PORT" \
		-c "$ctx" -fa on -ctk "$KV_TYPE" -ctv "$KV_TYPE" \
		--jinja --host "$HOST" --port "$PORT" ${extra[@]+"${extra[@]}"} &
	PIDS+=("$!")
	wait "$!" || true
}

main() {
	parse_args "$@"
	need curl
	need tar
	need python3
	need timeout

	if [[ "$MODE" == "dry" ]]; then
		resolve_release
		say "Release: $TAG"
		printf 'Vulkan build : %s\n' "$VK_URL"
		printf 'CUDA build   : %s\n' "$CUDA_URL"
		printf 'CUDA runtime : %s\n' "$CUDART_URL"
		printf 'Install dir  : %s\n' "$DIR"
		exit 0
	fi

	# Resolve the release only when something must be downloaded. A '--run' with
	# installed binaries must not depend on the GitHub API being reachable.
	if installed_tag; then
		say "Binaries already installed ($TAG), skipping release resolution and download"
	else
		resolve_release
		install_bins
		locate_bins
	fi

	VK_DEV="$(detect_vk_device)"
	say "AMD card is Vulkan device $VK_DEV; NVIDIA card is CUDA device $CUDA_DEVICE"

	if [[ "$MODE" == "setup" ]]; then
		say "Ready."
		printf 'Start it with:\n\n  %s --run /path/to/model.gguf [ctx]\n\n' "$0"
		printf 'Suggested for 16GB+16GB VRAM: 70B at IQ3_XS, ctx 16384.\n'
		printf 'Logs: %s/logs/\n' "$DIR"
		exit 0
	fi

	run_server "$MODEL" "${CTX_ARG:-$DEFAULT_CTX}" "$VK_DEV"
}

main "$@"
