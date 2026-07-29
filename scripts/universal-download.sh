#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${MODE:-url}"
SOURCE="${SOURCE:-}"
PLATFORM="${PLATFORM:-linux/arm64/v8}"
OUTPUT_NAME="${OUTPUT_NAME:-}"
COMPRESSION="${COMPRESSION:-none}"
DIST_DIR="${DIST_DIR:-dist}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  log "错误：$*"
  exit 1
}

sanitize_name() {
  printf '%s' "$1" | sed -E 's#[^A-Za-z0-9._-]+#-#g; s/^-+//; s/-+$//'
}

[[ -n "$SOURCE" ]] || fail "SOURCE 不能为空"
mkdir -p "$DIST_DIR"
rm -f "$DIST_DIR"/*

case "$MODE" in
  url)
    if [[ -z "$OUTPUT_NAME" ]]; then
      clean_url="${SOURCE%%\?*}"
      OUTPUT_NAME="$(basename "$clean_url")"
      [[ -n "$OUTPUT_NAME" && "$OUTPUT_NAME" != "/" && "$OUTPUT_NAME" != "." ]] || OUTPUT_NAME="download.bin"
    fi

    OUTPUT_NAME="$(sanitize_name "$OUTPUT_NAME")"
    [[ -n "$OUTPUT_NAME" ]] || OUTPUT_NAME="download.bin"

    log "下载 URL：$SOURCE"
    log "输出文件：$DIST_DIR/$OUTPUT_NAME"

    curl \
      --fail \
      --location \
      --show-error \
      --retry 5 \
      --retry-delay 3 \
      --retry-all-errors \
      --connect-timeout 30 \
      --output "$DIST_DIR/$OUTPUT_NAME.part" \
      "$SOURCE"

    mv "$DIST_DIR/$OUTPUT_NAME.part" "$DIST_DIR/$OUTPUT_NAME"
    ;;

  docker)
    log "拉取 Docker 镜像：$SOURCE"
    log "目标平台：$PLATFORM"

    docker pull --platform "$PLATFORM" "$SOURCE"

    actual_os="$(docker image inspect "$SOURCE" --format '{{.Os}}')"
    actual_arch="$(docker image inspect "$SOURCE" --format '{{.Architecture}}')"
    actual_variant="$(docker image inspect "$SOURCE" --format '{{.Variant}}')"

    log "实际镜像平台：${actual_os}/${actual_arch}${actual_variant:+/$actual_variant}"

    expected_os="${PLATFORM%%/*}"
    platform_rest="${PLATFORM#*/}"
    expected_arch="${platform_rest%%/*}"

    [[ "$actual_os" == "$expected_os" ]] || fail "镜像系统不匹配：期望 $expected_os，实际 $actual_os"
    [[ "$actual_arch" == "$expected_arch" ]] || fail "镜像架构不匹配：期望 $expected_arch，实际 $actual_arch"

    if [[ -z "$OUTPUT_NAME" ]]; then
      image_name="$(sanitize_name "$SOURCE")"
      platform_name="$(sanitize_name "$PLATFORM")"
      OUTPUT_NAME="${image_name}-${platform_name}.tar"
    fi

    OUTPUT_NAME="$(sanitize_name "$OUTPUT_NAME")"
    [[ "$OUTPUT_NAME" == *.tar ]] || OUTPUT_NAME="${OUTPUT_NAME}.tar"

    log "导出镜像：$DIST_DIR/$OUTPUT_NAME"
    docker save --output "$DIST_DIR/$OUTPUT_NAME" "$SOURCE"

    docker image inspect "$SOURCE" > "$DIST_DIR/${OUTPUT_NAME%.tar}-image-info.json"
    cat > "$DIST_DIR/${OUTPUT_NAME%.tar}-README.txt" <<EOF
Docker image: $SOURCE
Requested platform: $PLATFORM
Actual platform: ${actual_os}/${actual_arch}${actual_variant:+/$actual_variant}
Created at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')

Linux import command:
  docker load -i $OUTPUT_NAME

If this file is compressed with gzip:
  gzip -dc ${OUTPUT_NAME}.gz | docker load
EOF
    ;;

  *)
    fail "不支持的 MODE：$MODE，只能是 url 或 docker"
    ;;
esac

primary_file="$DIST_DIR/$OUTPUT_NAME"
[[ -s "$primary_file" ]] || fail "输出文件不存在或大小为 0：$primary_file"

case "$COMPRESSION" in
  none)
    log "不压缩输出文件"
    ;;
  gzip)
    log "使用 gzip 压缩：$primary_file"
    gzip -9 "$primary_file"
    primary_file="${primary_file}.gz"
    ;;
  zip)
    log "使用 zip 压缩：$primary_file"
    zip -9 -j "${primary_file}.zip" "$primary_file"
    rm -f "$primary_file"
    primary_file="${primary_file}.zip"
    ;;
  *)
    fail "不支持的 COMPRESSION：$COMPRESSION，只能是 none、gzip 或 zip"
    ;;
esac

(
  cd "$DIST_DIR"
  find . -maxdepth 1 -type f ! -name 'SHA256SUMS' -printf '%f\n' \
    | sort \
    | xargs -r sha256sum > SHA256SUMS
)

log "生成文件："
ls -lh "$DIST_DIR"
log "SHA256："
cat "$DIST_DIR/SHA256SUMS"
