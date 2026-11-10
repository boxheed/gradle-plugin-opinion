#!/bin/sh
set -e

echo "Installing Aider..."
(command -v aider >/dev/null) || (
  uv tool install --python 3.12 aider-chat
)

echo "Aider installed successfully."
aider --version
