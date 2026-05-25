# PostgreSQL 17 shadows — only active in interactive shells so scripts that
# call `psql` directly aren't affected. Skips if the *-17 binaries aren't
# installed so the file is safe on any machine.

if status is-interactive
    if command -q psql-17
        alias psql 'psql-17'
    end
    if command -q createdb-17
        alias createdb 'createdb-17'
    end
    if command -q createuser-17
        alias createuser 'createuser-17'
    end
end
