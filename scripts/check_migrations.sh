#!/bin/bash
# Check what migration files exist on the server

echo "🔍 Checking Migration Files"
echo "==========================="

for app_dir in apps/*/; do
    if [ -d "$app_dir" ]; then
        app_name=$(basename "$app_dir")
        migrations_dir="$app_dir/migrations"
        
        if [ -d "$migrations_dir" ]; then
            echo ""
            echo "📁 $app_name/migrations/:"
            
            # List all .py files in migrations directory
            migration_files=$(find "$migrations_dir" -name "*.py" | sort)
            
            if [ -z "$migration_files" ]; then
                echo "  (no migration files)"
            else
                for file in $migration_files; do
                    filename=$(basename "$file")
                    if [ "$filename" = "__init__.py" ]; then
                        echo "  ✅ $filename"
                    else
                        echo "  📄 $filename"
                    fi
                done
            fi
        fi
    fi
done

echo ""
echo "🗄️  Database Files:"
for db_file in db.sqlite3 database.db tulia.db; do
    if [ -f "$db_file" ]; then
        echo "  📄 $db_file ($(du -h "$db_file" | cut -f1))"
    fi
done

if [ ! -f "db.sqlite3" ] && [ ! -f "database.db" ] && [ ! -f "tulia.db" ]; then
    echo "  (no database files)"
fi

echo ""
echo "🐍 Python Environment:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "  ✅ Virtual environment active: $VIRTUAL_ENV"
else
    echo "  ❌ Virtual environment not active"
fi

echo "  🐍 Python: $(python --version 2>&1)"
echo "  📦 Django: $(python -c "import django; print(django.__version__)" 2>/dev/null || echo "Not installed")"