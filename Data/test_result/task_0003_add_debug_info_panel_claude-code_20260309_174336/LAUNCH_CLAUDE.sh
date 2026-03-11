#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
script agent_trajectory.log
node /Users/sejoonchang/.npm-global/lib/node_modules/@anthropic-ai/.claude-code-InSDvR7a/cli.js
