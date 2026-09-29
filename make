#!/bin/sh
# Runs GNU make even where /usr/bin/make refuses to start because the Xcode
# licence has not been accepted. Usage: ./make [-j8] [target ...]
cd "$(dirname "$0")" || exit 1
for m in gmake /Library/Developer/CommandLineTools/usr/bin/make \
         /Applications/Xcode.app/Contents/Developer/usr/bin/make make; do
  if command -v "$m" >/dev/null 2>&1 && "$m" --version >/dev/null 2>&1; then
    exec "$m" "$@"
  fi
done
echo "No working GNU make found." >&2
exit 1
