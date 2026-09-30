#!/bin/sh
# Every cloud container starts with a default git identity that is not Malik's.
# Set his identity globally (covers every repo in the container) and turn on
# the commit guard in this repo.
git config --global user.name malikbello
git config --global user.email 139644523+malikbello@users.noreply.github.com
git -C "$CLAUDE_PROJECT_DIR" config core.hooksPath .githooks
