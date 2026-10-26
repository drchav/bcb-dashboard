#!/usr/bin/env bash
# Publica o Painel SFN no servidor backoffice.dlip.com.br (bcb.dlip.com.br).
#   ./deploy/deploy.sh            envia o codigo e reinicia
#   ./deploy/deploy.sh --com-banco tambem envia dados/bcb.db (primeira vez / ressincronizar)
# Os usuarios (dados/usuarios.db) vivem so no servidor e nunca sao sobrescritos.
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
# Servidor/chave ficam fora do git (o IP de origem fica escondido atras do Cloudflare):
# crie deploy/deploy.env com, por exemplo:
#   SERVIDOR=root@<ip-do-servidor>
#   CHAVE=~/.ssh/id_rsa
[[ -f "$RAIZ/deploy/deploy.env" ]] && source "$RAIZ/deploy/deploy.env"
: "${SERVIDOR:?defina SERVIDOR em deploy/deploy.env}"
CHAVE="${CHAVE:-$HOME/.ssh/id_rsa}"
DESTINO=/srv/bcb-dashboard
SSH="ssh -i $CHAVE"

echo ">> preparando servidor"
$SSH $SERVIDOR "id bcb >/dev/null 2>&1 || useradd --system --home $DESTINO --shell /usr/sbin/nologin bcb;
                mkdir -p $DESTINO/dados && chown bcb:bcb $DESTINO/dados"

echo ">> enviando codigo"
rsync -az --delete -e "$SSH" \
  --exclude '.idea' --exclude '.DS_Store' --exclude '__pycache__' --exclude '*.iml' \
  --exclude 'dados/' --exclude '*.bat' --exclude '.git' --exclude 'deploy/deploy.env' \
  "$RAIZ/" "$SERVIDOR:$DESTINO/"

if [[ "${1:-}" == "--com-banco" ]]; then
  echo ">> enviando banco de dados (pode demorar)"
  python3 -c "import sqlite3; c=sqlite3.connect('$RAIZ/dados/bcb.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()"
  rsync -az --partial --progress -e "$SSH" "$RAIZ/dados/bcb.db" "$SERVIDOR:$DESTINO/dados/bcb.db.upload"
  $SSH $SERVIDOR "systemctl stop bcb-dashboard 2>/dev/null || true;
                  rm -f $DESTINO/dados/bcb.db-wal $DESTINO/dados/bcb.db-shm;
                  mv -f $DESTINO/dados/bcb.db.upload $DESTINO/dados/bcb.db"
fi

echo ">> instalando servicos, timer e nginx"
$SSH $SERVIDOR "set -e
  chown -R root:root $DESTINO
  find $DESTINO -path $DESTINO/dados -prune -o -type d -exec chmod 755 {} + -o -type f -exec chmod 644 {} +
  chmod 755 $DESTINO/deploy/*.sh && chown -R bcb:bcb $DESTINO/dados && chmod 750 $DESTINO/dados
  cp $DESTINO/deploy/bcb-dashboard.service $DESTINO/deploy/bcb-dashboard-atualizar.service \
     $DESTINO/deploy/bcb-dashboard-atualizar.timer /etc/systemd/system/
  cp $DESTINO/deploy/nginx-bcb.conf /etc/nginx/sites-available/bcb.conf
  ln -sf /etc/nginx/sites-available/bcb.conf /etc/nginx/sites-enabled/bcb.conf
  systemctl daemon-reload
  systemctl enable --now bcb-dashboard-atualizar.timer >/dev/null
  systemctl enable bcb-dashboard >/dev/null && systemctl restart bcb-dashboard
  nginx -t && systemctl reload nginx
  sleep 2; systemctl is-active bcb-dashboard"
echo ">> ok: https://bcb.dlip.com.br"
