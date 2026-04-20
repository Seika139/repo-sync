#!/usr/bin/env bash

print_c() {
  local no_newline=false
  if [[ $1 == '-n' ]]; then
    no_newline=true
    shift
  fi

  local color_name=$1
  shift

  local color_code
  case "$color_name" in
    black) color_code='00;30' ;;
    red) color_code='00;31' ;;
    green) color_code='00;32' ;;
    yellow) color_code='00;33' ;;
    blue) color_code='00;34' ;;
    magenta) color_code='00;35' ;;
    cyan) color_code='00;36' ;;
    white) color_code='01;37' ;;
    orange) color_code='38;2;250;180;100' ;;
    *)
      printf 'Unknown color: %s\n' "$color_name" >&2
      return 1
      ;;
  esac

  if "$no_newline"; then
    printf '\033[%sm%s\033[0m' "$color_code" "$*"
  else
    printf '\033[%sm%s\033[0m\n' "$color_code" "$*"
  fi
}

print_rgb() {
  local no_newline=false
  if [[ $1 == '-n' ]]; then
    no_newline=true
    shift
  fi

  local red=255
  local green=255
  local blue=255

  for color in red green blue; do
    if is_integer "$1"; then
      printf -v "$color" '%s' "$1"
      shift
    fi
  done

  local color_code="38;2;${red};${green};${blue}"

  if "$no_newline"; then
    printf '\033[%sm%s\033[0m' "$color_code" "$*"
  else
    printf '\033[%sm%s\033[0m\n' "$color_code" "$*"
  fi
}
