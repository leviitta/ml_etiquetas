"""
reset_test_user.py — Script de pruebas para resetear un usuario en la BD Postgres.

Uso:
    python3 scripts/reset_test_user.py                     # muestra estado actual
    python3 scripts/reset_test_user.py --email tu@email.com  # resetea ese usuario
    python3 scripts/reset_test_user.py --all               # borra TODOS los registros

Opciones:
    --email EMAIL   Email del usuario a resetear
    --all           Borra todos los usuarios (solo en dev)
    --show          Solo muestra el estado actual de la BD
"""
import argparse
import asyncpg
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Forzar UTF-8 en la terminal de Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

_db_user = os.getenv("DB_USER", "postgres")
_db_password = os.getenv("DB_PASSWORD", "mypassword123")
_db_name = os.getenv("DB_NAME", "mldb")

_env_url = os.getenv("DATABASE_URL")
if not _env_url or "${DB_USER}" in _env_url:
    DATABASE_URL = f"postgresql://{_db_user}:{_db_password}@localhost/{_db_name}"
else:
    DATABASE_URL = _env_url

async def conectar():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        print("   Asegúrate de que DATABASE_URL sea correcta y la BD esté corriendo.")
        sys.exit(1)

async def mostrar_estado(conn, email: str = None):
    print("\n" + "─" * 55)
    print("  📊  ESTADO ACTUAL DE LA BASE DE DATOS")
    print("─" * 55)

    if email:
        users = await conn.fetch("SELECT * FROM users WHERE email = $1", email)
    else:
        users = await conn.fetch("SELECT * FROM users")
        
    print(f"\n👤 Usuarios ({len(users)}):")
    for u in users:
        print(f"   • {u['email']}  —  {u['name']}  (desde {u['created_at']})")

    if email:
        from datetime import timezone
        from zoneinfo import ZoneInfo
        chile_tz = ZoneInfo("America/Santiago")
        now_chile = datetime.now(timezone.utc).astimezone(chile_tz)
        today_date = now_chile.date()
        
        total = await conn.fetchval("SELECT COUNT(*) FROM quota_usage WHERE email = $1", email)
        hoy = await conn.fetchval(
            "SELECT COUNT(*) FROM quota_usage WHERE email = $1 AND DATE(used_at AT TIME ZONE 'America/Santiago') = $2",
            email, today_date
        )
        print(f"\n📄 Documentos procesados (cuota):")
        print(f"   • Total: {total}   |   Hoy: {hoy}")
    else:
        usos = await conn.fetch("SELECT email, COUNT(*) as total FROM quota_usage GROUP BY email")
        print(f"\n📄 Usos de cuota ({sum(u['total'] for u in usos)} registros):")
        for u in usos:
            print(f"   • {u['email']}:  {u['total']} docs")

    if email:
        pagos = await conn.fetch("SELECT * FROM payments WHERE email = $1", email)
    else:
        pagos = await conn.fetch("SELECT * FROM payments")
        
    print(f"\n💳 Pagos ({len(pagos)}):")
    for p in pagos:
        plan = p['plan_type'] if 'plan_type' in dict(p) else 'premium'
        print(f"   • {p['email']}  plan={plan}  status={p['status']}  válido hasta={p['valid_until']}")

    print("\n" + "─" * 55 + "\n")

async def resetear_usuario(conn, email: str):
    existe = await conn.fetchval("SELECT COUNT(*) FROM users WHERE email = $1", email)

    if not existe:
        print(f"⚠️  El usuario '{email}' no existe en la BD.")
        return

    usos = await conn.fetchval("SELECT COUNT(*) FROM quota_usage WHERE email = $1", email)
    pagos = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE email = $1", email)

    print(f"\n🗑️  Reseteando usuario: {email}")
    print(f"   Eliminando {usos} registro(s) de quota_usage...")
    await conn.execute("DELETE FROM quota_usage WHERE email = $1", email)

    print(f"   Eliminando {pagos} registro(s) de payments...")
    await conn.execute("DELETE FROM payments WHERE email = $1", email)

    print(f"   Eliminando usuario de la tabla users...")
    await conn.execute("DELETE FROM users WHERE email = $1", email)

    print(f"\n✅ Usuario '{email}' reseteado.\n")

async def quitar_plan_pago(conn, email: str):
    pagos = await conn.fetchval("SELECT COUNT(*) FROM payments WHERE email = $1", email)

    if not pagos:
        print(f"⚠️  El usuario '{email}' no tiene un plan de pago activo.")
        return

    print(f"\n💸 Quitando plan de pago activo al usuario: {email}")
    await conn.execute("DELETE FROM payments WHERE email = $1", email)
    print(f"✅ Se eliminó {pagos} pago(s). El usuario vuelve a la cuota gratuita.\n")

async def resetear_todo(conn):
    await conn.execute("DELETE FROM quota_usage")
    await conn.execute("DELETE FROM payments")
    await conn.execute("DELETE FROM users")
    print("\n✅ Base de datos limpiada completamente.\n")

async def run_main():
    parser = argparse.ArgumentParser(description="Resetear usuarios en Postgres.")
    parser.add_argument("--email", help="Email del usuario a resetear")
    parser.add_argument("--all",   action="store_true", help="Borrar TODOS los registros")
    parser.add_argument("--show",  action="store_true", help="Solo mostrar estado actual")
    parser.add_argument("--quitar-plan", action="store_true", help="Quita el plan de pago")
    args = parser.parse_args()

    conn = await conectar()

    try:
        if not args.email and not args.all:
            await mostrar_estado(conn)
            return

        if args.show or (args.email and not args.all):
            if args.email:
                await mostrar_estado(conn, args.email)

        if args.all:
            confirmar = input("⚠️  ¿Borrar TODOS los usuarios y registros? (s/N): ").strip().lower()
            if confirmar == "s":
                await resetear_todo(conn)
                await mostrar_estado(conn)
            else:
                print("Cancelado.")
        elif args.email:
            if args.quitar_plan:
                await quitar_plan_pago(conn, args.email)
            else:
                await resetear_usuario(conn, args.email)
            await mostrar_estado(conn, args.email)
    finally:
        await conn.close()

def main():
    asyncio.run(run_main())

if __name__ == "__main__":
    main()
