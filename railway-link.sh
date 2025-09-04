#!/bin/bash
# Script to handle Railway linking with automatic input
expect -c "
spawn railway link
expect \"Select a project\"
send \"\r\"
expect eof
"