#!/bin/sh
set -eu

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__CVM_RUNTIME_CONFIG__ = {
  apiBaseUrl: ''
};
EOF
