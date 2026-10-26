#!/usr/bin/env bash
# Atualizacao diaria: coleta numa COPIA do banco e so troca se der certo.
# Se o BCB estiver fora do ar ou a coleta falhar, o painel segue com os dados de ontem.
set -euo pipefail
RAIZ=/srv/bcb-dashboard
DADOS=$RAIZ/dados
NOVO=$DADOS/bcb.db.novo
cd "$RAIZ/backend"

rm -f "$NOVO" "$NOVO-wal" "$NOVO-shm"
echo ">> copiando banco atual"
runuser -u bcb -- python3 -c "
import sqlite3, sys
src = sqlite3.connect('file:$DADOS/bcb.db?mode=ro', uri=True)
dst = sqlite3.connect('$NOVO'); src.backup(dst); dst.close(); src.close()"

echo ">> coletando dados do BCB"
runuser -u bcb -- env BCB_DB_PATH="$NOVO" python3 -u pipeline.py

echo ">> conferindo o resultado"
runuser -u bcb -- python3 -c "
import sqlite3, sys
c = sqlite3.connect('$NOVO')
assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'integrity_check falhou'
n = c.execute('SELECT COUNT(*) FROM valores').fetchone()[0]
assert n > 100000, f'poucas linhas em valores: {n}'
c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.execute('PRAGMA journal_mode=DELETE'); c.close()
print('   ok,', n, 'linhas em valores')"

echo ">> trocando o banco e reiniciando o painel"
systemctl stop bcb-dashboard
rm -f "$DADOS/bcb.db-wal" "$DADOS/bcb.db-shm"
mv -f "$DADOS/bcb.db" "$DADOS/bcb.db.anterior"
mv -f "$NOVO" "$DADOS/bcb.db"
chmod 640 "$DADOS/bcb.db"
systemctl start bcb-dashboard
echo ">> pronto"
