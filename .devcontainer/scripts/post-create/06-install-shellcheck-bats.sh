#!/bin/sh
set -e

echo "Installing ShellCheck and Bats..."

(command -v shellcheck >/dev/null && command -v bats >/dev/null) || (
  sudo apt-get update -qq &&
  sudo apt-get install -y --no-install-recommends shellcheck bats
)

echo "ShellCheck and Bats installed successfully."
shellcheck --version
bats --version
