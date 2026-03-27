#!/bin/sh
# Maven Wrapper script

# OS specific support
cygwin=false
case "$(uname)" in
  CYGWIN*) cygwin=true ;;
esac

# Resolve project base directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Download maven wrapper if needed
MAVEN_VERSION="3.9.6"
MAVEN_URL="https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz"
MAVEN_HOME="$HOME/.m2/wrapper/dists/apache-maven-${MAVEN_VERSION}"

if [ ! -f "$MAVEN_HOME/bin/mvn" ]; then
    echo "Downloading Maven ${MAVEN_VERSION}..."
    mkdir -p "$MAVEN_HOME"
    curl -fsSL "$MAVEN_URL" | tar -xz -C "$MAVEN_HOME" --strip-components=1
fi

exec "$MAVEN_HOME/bin/mvn" "$@"

