import os
import sys
import threading
import webbrowser
import time
import socket

# Définit le chemin de base
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, BASE_DIR)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def lancer_migrations():
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)


def lancer_serveur():
    from django.core.management import call_command
    call_command('runserver', '0.0.0.0:8000', '--noreload')


def ouvrir_navigateur():
    time.sleep(3)
    webbrowser.open('http://127.0.0.1:8000')


if __name__ == '__main__':
    ip_locale = get_local_ip()

    print("=" * 50)
    print("   STOCKMANAGER - Demarrage...")
    print("=" * 50)
    print()
    print("Initialisation de la base de donnees...")

    lancer_migrations()

    print("Base de donnees prete !")
    print()
    print("=" * 50)
    print("  STOCKMANAGER EST DEMARRE !")
    print("-" * 50)
    print(f"  Acces local  : http://127.0.0.1:8000")
    print(f"  Acces reseau : http://{ip_locale}:8000")
    print()
    print("  Les telephones connectes au WiFi")
    print(f"  de ce PC tapent : http://{ip_locale}:8000")
    print("=" * 50)
    print()
    print("  Ne fermez pas cette fenetre !")
    print("  Minimisez-la seulement.")
    print()

    threading.Thread(target=ouvrir_navigateur, daemon=True).start()
    lancer_serveur()