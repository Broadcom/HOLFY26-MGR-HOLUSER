#!/bin/bash

# Define password length and special characters
PASS_LEN=16
SPECIAL_CHARS="!-"

# Generate the special character
SPEC_CHAR=$(echo "$SPECIAL_CHARS" | fold -w1 | shuf | head -n1)

# Generate a base password one character shorter
BASE_PASS=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9!-' | head -c $((PASS_LEN-1)))

# Determine a random position (not the first character)
POS=$((RANDOM % (PASS_LEN-1) + 1))

# Insert the special character and print the final password
FINAL_PASS="${BASE_PASS:0:$POS}${SPEC_CHAR}${BASE_PASS:$POS}"
echo "$FINAL_PASS"
