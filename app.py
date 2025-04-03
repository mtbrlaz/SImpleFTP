import eel
import os
import ftplib
import shutil
import configparser
import base64
import io
import posixpath

eel.init('web')

ftp = None
INIFILE = 'winscp.ini'  # kam ukladáme sessions

###############################################################################
# Obfuskovanie / Deobfuskácia hesiel (WinSCP style)
###############################################################################

def obfuscate_winscp_password(password: str) -> str:
    if not password:
        return ""
    key = [0xFF, 0xA3, 0xB1, 0x9E, 0x5C, 0x34, 0x81, 0xEE]
    data = password.encode('utf-8')
    obf = bytearray(len(data))
    for i in range(len(data)):
        obf[i] = data[i] ^ key[i % len(key)]
    encoded = base64.b64encode(obf).decode('ascii')
    return encoded

def deobfuscate_winscp_password(obf_string: str) -> str:
    if not obf_string.startswith("obfuscated:"):
        return obf_string
    encoded = obf_string[len("obfuscated:"):]
    raw = base64.b64decode(encoded)
    key = [0xFF, 0xA3, 0xB1, 0x9E, 0x5C, 0x34, 0x81, 0xEE]
    decoded = bytearray(len(raw))
    for i in range(len(raw)):
        decoded[i] = raw[i] ^ key[i % len(key)]
    return decoded.decode('utf-8', errors='replace')

###############################################################################
# Správa WinSCP sessions v .ini (obfuskovaný formát)
###############################################################################

@eel.expose
def load_winscp_sessions():
    config = configparser.ConfigParser()
    config.read(INIFILE, encoding='utf-8')
    sessions = []
    for section in config.sections():
        if section.startswith("Sessions\\"):
            sess_name = section.split("\\", 1)[1]
            host = config[section].get("HostName", "")
            user = config[section].get("UserName", "")
            password_str = config[section].get("Password", "")
            real_pass = deobfuscate_winscp_password(password_str)
            sessions.append({
                "session_name": sess_name,
                "host": host,
                "user": user,
                "password": real_pass
            })
    return sessions

@eel.expose
def add_winscp_session(host, user, password, session_name):
    config = configparser.ConfigParser()
    config.read(INIFILE, encoding='utf-8')
    section = f"Sessions\\{session_name}"
    if section not in config.sections():
        config.add_section(section)

    config[section]["HostName"] = host
    config[section]["UserName"] = user
    obf = obfuscate_winscp_password(password)
    config[section]["Password"] = f"obfuscated:{obf}"
    config[section]["PortNumber"] = "21"
    config[section]["FSProtocol"] = "5"
    config[section]["Protocol"] = "2"

    with open(INIFILE, 'w', encoding='utf-8') as f:
        config.write(f)

    return "Session bola pridaná/aktualizovaná."

@eel.expose
def delete_winscp_session(session_name):
    config = configparser.ConfigParser()
    config.read(INIFILE, encoding='utf-8')
    section = f"Sessions\\{session_name}"
    if section in config.sections():
        config.remove_section(section)
        with open(INIFILE, 'w', encoding='utf-8') as f:
            config.write(f)
        return f"Session '{session_name}' bola odstránená."
    else:
        return f"Session '{session_name}' neexistuje."

###############################################################################
# Pripojenie k FTP
###############################################################################

@eel.expose
def connect_to_ftp(host, username, password):
    global ftp
    try:
        ftp = ftplib.FTP(host)
        ftp.login(username, password)
        return "Pripojenie úspešné."
    except Exception as e:
        ftp = None
        return f"Chyba: {str(e)}"

###############################################################################
# Listing priečinkov (robustné parsovanie)
###############################################################################

@eel.expose
def list_remote_dir(path="."):
    """Použijeme robustné parsovanie s split(None, 8)."""
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."

    try:
        ftp.cwd('/' + path)
        lines = []
        ftp.retrlines('LIST', lines.append)
        results = []
        print(lines)
        for line in lines:
            parts = line.split(None, 8)
            if len(parts) < 9:
                # Môže sa stať, ak je server výstredný
                # Skúsime fallback
                name = parts[-1] if parts else '?'
                perms = parts[0] if parts else ''
            else:
                perms = parts[0]
                name = parts[8].strip()

            is_dir = perms.startswith('d')
            is_symlink = perms.startswith('l')
            link_target = None
            if is_symlink:
                arrow_pos = name.find("->")
                if arrow_pos >= 0:
                    # name = "linkname -> target"
                    left_side = name[:arrow_pos].strip()
                    right_side = name[arrow_pos+2:].strip()
                    name = left_side
                    link_target = right_side

            results.append({
                "name": name,
                "is_dir": is_dir,
                "is_symlink": is_symlink,
                "link_target": link_target
            })
        return results
    except Exception as e:
        return f"Chyba: {str(e)}"

@eel.expose
def list_local_dir(path="."):
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return f"Chyba: cesta '{abs_path}' neexistuje"
        if not os.path.isdir(abs_path):
            return f"Chyba: cesta '{abs_path}' nie je priečinok"

        entries = os.listdir(abs_path)
        results = []
        for name in entries:
            fullpath = os.path.join(abs_path, name)
            isdir = os.path.isdir(fullpath)
            results.append({
                "name": name,
                "is_dir": isdir
            })
        return results
    except Exception as e:
        return f"Chyba: {str(e)}"

###############################################################################
# Kopírovanie súborov (upload/download)
###############################################################################

@eel.expose
def download_file(remote_file, local_file):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        with open(local_file, 'wb') as f:
            ftp.retrbinary(f'RETR {remote_file}', f.write)
        return "Súbor stiahnutý."
    except Exception as e:
        return f"Chyba pri sťahovaní súboru: {str(e)}"

@eel.expose
def upload_file(local_file, remote_file):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        with open(local_file, 'rb') as f:
            ftp.storbinary(f'STOR {remote_file}', f)
        return "Súbor nahraný."
    except Exception as e:
        return f"Chyba pri nahrávaní súboru: {str(e)}"

@eel.expose
def upload_folder(local_folder, remote_folder):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        try:
            ftp.mkd(remote_folder)
        except ftplib.error_perm:
            pass

        for root, dirs, files in os.walk(local_folder):
            rel_path = os.path.relpath(root, local_folder)
            if rel_path == '.':
                remote_subdir = remote_folder
            else:
                remote_subdir = posixpath.join(remote_folder, rel_path)
            try:
                ftp.mkd(remote_subdir)
            except ftplib.error_perm:
                pass
            for file in files:
                lf = os.path.join(root, file)
                rf = posixpath.join(remote_subdir, file)
                with open(lf, 'rb') as f:
                    ftp.storbinary(f'STOR {rf}', f)

        return "Priečinok nahraný."
    except Exception as e:
        return f"Chyba pri nahrávaní priečinka: {str(e)}"

@eel.expose
def download_folder(remote_folder, local_folder):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."

    try:
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        original_cwd = ftp.pwd()
        ftp.cwd(remote_folder)

        lines = []
        ftp.retrlines('LIST', lines.append)
        for line in lines:
            parts = line.split(None, 8)
            if len(parts) < 9:
                name = parts[-1] if parts else '?'
                perms = parts[0] if parts else ''
            else:
                perms = parts[0]
                name = parts[8]

            if perms.startswith('d'):
                # priečinok
                new_remote = posixpath.join(remote_folder, name)
                new_local = os.path.join(local_folder, name)
                download_folder(new_remote, new_local)
            else:
                # súbor
                new_remote = posixpath.join(remote_folder, name)
                new_local = os.path.join(local_folder, name)
                with open(new_local, 'wb') as f:
                    ftp.retrbinary(f'RETR {new_remote}', f.write)

        ftp.cwd(original_cwd)
        return "Priečinok stiahnutý."
    except Exception as e:
        return f"Chyba pri sťahovaní priečinka: {str(e)}"

###############################################################################
# Premenovanie, mazanie, nové súbory / priečinky
###############################################################################

@eel.expose
def rename_local_file(old_path, new_path):
    try:
        os.rename(old_path, new_path)
        return "Lokálny súbor/priečinok premenovaný."
    except Exception as e:
        return f"Chyba pri premenovaní lokálne: {str(e)}"

@eel.expose
def rename_remote_file(old_path, new_path):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        ftp.rename(old_path, new_path)
        return "Vzdialený súbor/priečinok premenovaný."
    except Exception as e:
        return f"Chyba pri premenovaní na FTP: {str(e)}"

@eel.expose
def create_local_file(path):
    try:
        if os.path.exists(path):
            return "Súbor už existuje."
        with open(path, 'w', encoding='utf-8') as f:
            pass
        return "Nový lokálny súbor vytvorený."
    except Exception as e:
        return f"Chyba pri vytváraní lokálneho súboru: {str(e)}"

@eel.expose
def create_remote_file(path):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        empty_data = io.BytesIO(b"")
        ftp.storbinary(f"STOR {path}", empty_data)
        return "Nový vzdialený súbor vytvorený."
    except Exception as e:
        return f"Chyba pri vytváraní vzdialeného súboru: {str(e)}"

@eel.expose
def create_local_folder(path):
    try:
        os.mkdir(path)
        return "Nový lokálny priečinok vytvorený."
    except Exception as e:
        return f"Chyba pri vytváraní lokálneho priečinka: {str(e)}"

@eel.expose
def create_remote_folder(path):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        ftp.mkd(path)
        return "Nový vzdialený priečinok vytvorený."
    except Exception as e:
        return f"Chyba pri vytváraní vzdialeného priečinka: {str(e)}"

@eel.expose
def delete_local(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return "Lokálna položka bola vymazaná."
    except Exception as e:
        return f"Chyba pri mazaní lokálnej položky: {str(e)}"

@eel.expose
def delete_remote(path):
    """Rekurzívne zmazanie súboru/priečinka."""
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."

    # Skúsime zmazať ako súbor
    try:
        ftp.delete(path)
        return "Vzdialená položka bola vymazaná (súbor)."
    except ftplib.error_perm:
        # Ak to nie je súbor, skúsime priečinok rekurzívne
        def ftp_recursive_delete(dir_path):
            lines = []
            ftp.retrlines(f'LIST {dir_path}', lines.append)
            for line in lines:
                p = line.split(None, 8)
                if len(p) < 9:
                    nm = p[-1] if p else '?'
                    pm = p[0] if p else ''
                else:
                    pm = p[0]
                    nm = p[8]
                if nm in ('.', '..'):
                    continue
                full = posixpath.join(dir_path, nm)
                if pm.startswith('d'):
                    ftp_recursive_delete(full)
                else:
                    ftp.delete(full)
            ftp.rmd(dir_path)

        try:
            ftp_recursive_delete(path)
            return "Vzdialená položka bola vymazaná (priečinok)."
        except Exception as e:
            return f"Chyba pri mazaní priečinka na FTP: {str(e)}"

###############################################################################
# Editor: načítanie/uloženie obsahu
###############################################################################

@eel.expose
def read_file_content(path, is_remote):
    if is_remote:
        global ftp
        if ftp is None:
            return "Chyba: Nie si pripojený k FTP serveru."
        mem = io.BytesIO()
        try:
            ftp.retrbinary('RETR ' + path, mem.write)
            data = mem.getvalue().decode('utf-8', errors='replace')
            return data
        except Exception as e:
            return f"Chyba pri čítaní remote: {str(e)}"
    else:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            return f"Chyba pri čítaní lokálne: {str(e)}"

@eel.expose
def save_file_content(path, is_remote, new_content):
    if is_remote:
        global ftp
        if ftp is None:
            return "Chyba: Nie si pripojený k FTP serveru."
        try:
            mem = io.BytesIO(new_content.encode('utf-8', errors='replace'))
            ftp.storbinary(f"STOR {path}", mem)
            return "Zmeny uložené na vzdialenom serveri."
        except Exception as e:
            return f"Chyba pri ukladaní remote: {str(e)}"
    else:
        try:
            with open(path, 'w', encoding='utf-8', errors='replace') as f:
                f.write(new_content)
            return "Zmeny uložené lokálne."
        except Exception as e:
            return f"Chyba pri ukladaní lokálne: {str(e)}"


if __name__ == '__main__':
    eel.start('index.html', size=(1000, 600))
