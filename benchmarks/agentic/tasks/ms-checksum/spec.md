# Spec

For every file directly inside /data compute a contribution:

- If the file name ends in .txt or .md: (number of lines) multiplied by
  (length of the file name, including the extension).
- Otherwise: (file size in bytes) modulo 7.

Sum the contributions over all files and write the total to
/answer.txt as a plain integer. A trailing newline at the end of a
file does not start a new line.
