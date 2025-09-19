#!/bin/python3
"""
Buildozer action - Version corrigée pour GitHub Actions
========================================================

Version modifiée qui évite les problèmes de permissions sudo dans GitHub Actions.

Corrections apportées :
- Suppression des commandes sudo chown (lignes 21 et 31)
- Remplacement de la commande sudo pour GITHUB_OUTPUT
- Gestion des permissions adaptée à GitHub Actions
- AJOUT: Installation de autopoint et gettext pour pandas/liblzma
"""

import os
import subprocess
import sys
from os import environ as env


def main():
    repository_root = os.path.abspath(env["INPUT_REPOSITORY_ROOT"])
    # CORRECTION 1: Supprimer le changement de propriétaire au début
    # change_owner(env["USER"], repository_root)  # Ligne supprimée
    fix_home()
    install_system_deps()  # CORRECTION 6: Installer les dépendances système manquantes
    configure_pip()  # CORRECTION 5: Configurer pip avant d'installer buildozer
    install_buildozer(env["INPUT_BUILDOZER_VERSION"])
    apply_buildozer_settings()
    change_directory(env["INPUT_REPOSITORY_ROOT"], env["INPUT_WORKDIR"])
    apply_patches()
    run_command(env["INPUT_COMMAND"])
    set_output(env["INPUT_REPOSITORY_ROOT"], env["INPUT_WORKDIR"])
    # CORRECTION 2: Supprimer le retour à root
    # change_owner("root", repository_root)  # Ligne supprimée


def change_owner(user, repository_root):
    """
    FONCTION DÉSACTIVÉE - Cause des problèmes dans GitHub Actions
    GitHub Actions gère automatiquement les permissions correctement
    """
    print(f"::notice::Skipping chown operation - not needed in GitHub Actions")
    # subprocess.check_call(["sudo", "chown", "-R", user, repository_root])


def fix_home():
    # GitHub sets HOME to /github/home, but Buildozer is installed to /home/user. Change HOME to user's home
    env["HOME"] = env["HOME_DIR"]


def install_buildozer(buildozer_version):
    # Install required Buildozer version
    print("::group::Installing Buildozer")
    # CORRECTION 4: Ajouter --break-system-packages pour Ubuntu 24.04
    pip_install = [sys.executable] + "-m pip install --user --upgrade --break-system-packages".split()
    if buildozer_version == "stable":
        # Install stable buildozer from PyPI
        subprocess.check_call([*pip_install, "buildozer"])
    elif os.path.exists(buildozer_version) and os.path.exists(
        os.path.join(buildozer_version, "buildozer", "__init__.py")
    ):
        # Install from local directory
        subprocess.check_call([*pip_install, buildozer_version])
    elif buildozer_version.startswith("git+"):
        # Install from specified git+ link
        subprocess.check_call([*pip_install, buildozer_version])
    elif buildozer_version == "":
        # Just do nothing
        print(
            "::warning::Buildozer is not installed because "
            "specified buildozer_version is nothing."
        )
    else:
        # Install specified ref from repository
        subprocess.check_call(
            [
                *pip_install,
                f"git+https://github.com/kivy/buildozer.git@{buildozer_version}",
            ]
        )
    print("::endgroup::")


def install_system_deps():
    # Install missing system dependencies INCLUDING autopoint for pandas/liblzma
    print("::group::Installing system dependencies")
    try:
        print("::notice::Updating package lists...")
        subprocess.check_call(["apt", "update", "-qq"])
        
        print("::notice::Installing build tools and dependencies...")
        subprocess.check_call(["apt", "install", "-y", 
                              "wget", 
                              "curl", 
                              "gettext",           # Contient autopoint
                              "autopoint",         # Spécifiquement pour l'erreur
                              "autotools-dev", 
                              "autoconf", 
                              "automake", 
                              "libtool",           # Nécessaire pour liblzma
                              "build-essential",
                              "pkg-config"])       # Utile pour la compilation
        print("::notice::Successfully installed all build tools and dependencies")
        
        # Vérifier que autopoint est bien installé
        try:
            subprocess.check_call(["which", "autopoint"], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
            print("::notice::autopoint successfully installed and available")
        except subprocess.CalledProcessError:
            print("::warning::autopoint not found after installation")
            
    except subprocess.CalledProcessError as e:
        print(f"::error::Could not install system dependencies: {e}")
        print("::error::This may cause build failures for pandas and other native dependencies")
        sys.exit(1)  # Arrêter si l'installation échoue
    print("::endgroup::")


def configure_pip():
    # Configure pip pour éviter l'erreur externally-managed-environment
    print("::group::Configuring pip for externally-managed environment")
    pip_conf_dir = os.path.expanduser("~/.pip")
    pip_conf = os.path.join(pip_conf_dir, "pip.conf")
    os.makedirs(pip_conf_dir, exist_ok=True)
    with open(pip_conf, "w") as f:
        f.write("[global]\nbreak-system-packages = true\n")
    print(f"::notice::Created pip.conf with break-system-packages = true")
    print("::endgroup::")


def apply_buildozer_settings():
    # Buildozer settings to disable interactions
    env["BUILDOZER_WARN_ON_ROOT"] = "0"
    env["APP_ANDROID_ACCEPT_SDK_LICENSE"] = "1"
    # Do not allow to change directories
    env["BUILDOZER_BUILD_DIR"] = "./.buildozer"
    env["BUILDOZER_BIN"] = "./bin"


def change_directory(repository_root, workdir):
    directory = os.path.join(repository_root, workdir)
    # Change directory to workir
    if not os.path.exists(directory):
        print("::error::Specified workdir is not exists.")
        exit(1)
    os.chdir(directory)


def apply_patches():
    # Apply patches
    print("::group::Applying patches to Buildozer")
    try:
        import importlib
        import site

        importlib.reload(site)
        globals()["buildozer"] = importlib.import_module("buildozer")
    except ImportError:
        print(
            "::error::Cannot apply patches to buildozer (ImportError). "
            "Update buildozer-action to new version or create a Bug Request"
        )
        print("::endgroup::")
        return

    print("Changing global_buildozer_dir")
    source = open(buildozer.__file__, "r", encoding="utf-8").read()
    new_source = source.replace(
        """
    @property
    def global_buildozer_dir(self):
        return join(expanduser('~'), '.buildozer')
""",
        f"""
    @property
    def global_buildozer_dir(self):
        return '{env["GITHUB_WORKSPACE"]}/{env["INPUT_REPOSITORY_ROOT"]}/.buildozer_global'
""",
    )
    if new_source == source:
        print(
            "::warning::Cannot change global buildozer directory. "
            "Update buildozer-action to new version or create a Bug Request"
        )
    open(buildozer.__file__, "w", encoding="utf-8").write(new_source)
    print("::endgroup::")


def run_command(command):
    # Run command
    retcode = subprocess.check_call(command, shell=True)
    if retcode:
        print(f'::error::Error while executing command "{command}"')
        exit(1)


def set_output(repository_root, workdir):
    if not os.path.exists("bin"):
        print(
            "::error::Output directory does not exist. See Buildozer log for error"
        )
        exit(1)
    filename = [
        file
        for file in os.listdir("bin")
        if os.path.isfile(os.path.join("bin", file))
    ][0]
    path = os.path.normpath(
        os.path.join(repository_root, workdir, "bin", filename)
    )
    
    # CORRECTION 3: Écrire directement dans GITHUB_OUTPUT sans sudo
    try:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output_file:
            output_file.write(f'filename={path}\n')
        print(f"::notice::Output file set: {path}")
    except Exception as e:
        print(f"::warning::Could not write to GITHUB_OUTPUT: {e}")
        # Fallback: essayer sans sudo d'abord, puis avec si nécessaire
        try:
            subprocess.check_call([
                "bash", "-c", 
                f"echo 'filename={path}' >> {os.environ['GITHUB_OUTPUT']}"
            ])
        except subprocess.CalledProcessError:
            print("::error::Failed to set output file")
            exit(1)


if __name__ == "__main__":
    main()
