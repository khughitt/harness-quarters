#!/usr/bin/env bash
# Claude Code status line - converted from ~/.bashrc PS1: [\u@\h \W]\$
# (trailing "\$" prompt-terminator dropped per statusline conversion rules)

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model=$(echo "$input" | jq -r '.model.display_name // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

user=$(whoami)
host=$(hostname -s)
dir=$(basename "$cwd")

# Git branch (skip optional locks to avoid contention)
git_branch=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" -c core.hooksPath=/dev/null symbolic-ref --short HEAD 2>/dev/null \
             || git -C "$cwd" -c core.hooksPath=/dev/null rev-parse --short HEAD 2>/dev/null)
    if [ -n "$branch" ]; then
        git_branch=" ($branch)"
    fi
fi

# Context usage indicator
ctx_info=""
if [ -n "$used_pct" ]; then
    used_int=${used_pct%.*}
    ctx_info=" [ctx: ${used_int}%]"
fi

# ANSI colors (dimmed to suit the terminal's dimmed status-line rendering)
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GRAY='\033[0;90m'
RESET='\033[0m'

printf "${CYAN}[%s@%s %s]${RESET}${MAGENTA}%s${RESET}${GRAY}  %s%s${RESET}" \
    "$user" \
    "$host" \
    "$dir" \
    "$git_branch" \
    "$model" \
    "$ctx_info"
