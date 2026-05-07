"""
reset_test_user.py — Script de pruebas para resetear un usuario en la BD local.

Uso:
    uv run python scripts/reset_test_user.py                     # muestra estado actual
    uv run python scripts/reset_test_user.py --email tu@email.com  # resetea ese usuario
    uv run python scripts/reset_test_user.py --all               # borra TODOS los registros

Opciones:
    --email EMAIL   Email del usuario a resetear
    --all           Borra todos los usuarios (solo en dev)
    --show          Solo muestra el estado actual de la BD (default si no se pasa nada)
"""
import argparse
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

# Forzar UTF-8 en la terminal de Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Ruta de la BD (igual que en database.py)
DB_PATH = os.getenv("DB_PATH", "app/db/app.db")


def conectar():
    if not Path(DB_PATH).exists():
        print(f"❌ No existe la base de datos en: {DB_PATH}")
        print("   Inicia el servidor al menos una vez para crearla.")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def mostrar_estado(conn, email: str = None):
    """Muestra un resumen de los registros actuales."""
    cur = conn.cursor()

    print("\n" + "─" * 55)
    print("  📊  ESTADO ACTUAL DE LA BASE DE DATOS")
    print("─" * 55)

    # Usuarios
    if email:
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    else:
        cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    print(f"\n👤 Usuarios ({len(users)}):")
    for u in users:
        print(f"   • {u['email']}  —  {u['name']}  (desde {u['created_at']})")

    # Usos de cuota
    if email:
        cur.execute("SELECT COUNT(*) as cnt FROM quota_usage WHERE email = ?", (email,))
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT COUNT(*) as cnt FROM quota_usage WHERE email = ? AND date(used_at) = date('now')",
            (email,)
        )
        total = cur.fetchone()["cnt"]
        hoy   = cur2.fetchone()["cnt"]
        print(f"\n📄 Documentos procesados (cuota):")
        print(f"   • Total: {total}   |   Hoy: {hoy}")
    else:
        cur.execute(
            "SELECT email, COUNT(*) as total FROM quota_usage GROUP BY email"
        )
        usos = cur.fetchall()
        print(f"\n📄 Usos de cuota ({sum(u['total'] for u in usos)} registros):")
        for u in usos:
            print(f"   • {u['email']}:  {u['total']} docs")

    # Pagos
    if email:
        cur.execute("SELECT * FROM payments WHERE email = ?", (email,))
    else:
        cur.execute("SELECT * FROM payments")
    pagos = cur.fetchall()
    print(f"\n💳 Pagos ({len(pagos)}):")
    for p in pagos:
        print(f"   • {p['email']}  status={p['status']}  válido hasta={p['valid_until']}")

    print("\n" + "─" * 55 + "\n")


def resetear_usuario(conn, email: str):
    """Elimina todos los registros del usuario indicado."""
    cur = conn.cursor()

    # Contar antes
    cur.execute("SELECT COUNT(*) as cnt FROM quota_usage WHERE email = ?", (email,))
    usos = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) as cnt FROM payments WHERE email = ?", (email,))
    pagos = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE email = ?", (email,))
    existe = cur.fetchone()["cnt"]

    if not existe:
        print(f"⚠️  El usuario '{email}' no existe en la BD.")
        return

    print(f"\n🗑️  Reseteando usuario: {email}")
    print(f"   Eliminando {usos} registro(s) de quota_usage...")
    cur.execute("DELETE FROM quota_usage WHERE email = ?", (email,))

    print(f"   Eliminando {pagos} registro(s) de payments...")
    cur.execute("DELETE FROM payments WHERE email = ?", (email,))

    print(f"   Eliminando usuario de la tabla users...")
    cur.execute("DELETE FROM users WHERE email = ?", (email,))

    conn.commit()
    print(f"\n✅ Usuario '{email}' reseteado. La próxima vez que inicie sesión")
    print(f"   será tratado como usuario completamente nuevo.\n")


def quitar_premium(conn, email: str):
    """Elimina el registro de pago (Premium) del usuario sin borrar su historial."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM payments WHERE email = ?", (email,))
    pagos = cur.fetchone()["cnt"]

    if not pagos:
        print(f"⚠️  El usuario '{email}' no tiene una suscripción Premium activa.")
        return

    print(f"\n💸 Quitando suscripción Premium al usuario: {email}")
    cur.execute("DELETE FROM payments WHERE email = ?", (email,))
    conn.commit()
    print(f"✅ Se eliminó {pagos} pago(s). El usuario vuelve a la cuota gratuita.\n")


def resetear_todo(conn):
    """Borra TODOS los registros de todas las tablas (solo dev)."""
    cur = conn.cursor()
    cur.execute("DELETE FROM quota_usage")
    cur.execute("DELETE FROM payments")
    cur.execute("DELETE FROM users")
    conn.commit()
    print("\n✅ Base de datos limpiada completamente.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Herramienta de dev para resetear usuarios en la BD local."
    )
    parser.add_argument("--email", help="Email del usuario a resetear")
    parser.add_argument("--all",   action="store_true", help="Borrar TODOS los registros")
    parser.add_argument("--show",  action="store_true", help="Solo mostrar estado actual")
    parser.add_argument("--quitar-premium", action="store_true", help="Quita la suscripción premium del usuario (requiere --email)")
    args = parser.parse_args()

    conn = conectar()

    # Sin argumentos → solo mostrar
    if not args.email and not args.all:
        mostrar_estado(conn)
        return

    if args.show or (args.email and not args.all):
        if args.email:
            mostrar_estado(conn, args.email)

    if args.all:
        confirmar = input("⚠️  ¿Borrar TODOS los usuarios y registros? (s/N): ").strip().lower()
        if confirmar == "s":
            resetear_todo(conn)
            mostrar_estado(conn)
        else:
            print("Cancelado.")
    elif args.email:
        if args.quitar_premium:
            quitar_premium(conn, args.email)
        else:
            resetear_usuario(conn, args.email)
        mostrar_estado(conn, args.email)

    conn.close()


if __name__ == "__main__":
    main()
