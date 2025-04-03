import eel
import ftplib
import os
import posixpath
import configparser
import base64
import io
import shutil

eel.init('web')

ftp = None
INIFILE = 'winscp.ini'

###############################################################################
# Obfuskovanie / Deobfuskácia hesiel v štýle WinSCP
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
# Správa WinSCP sessions v .ini
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
# FTP funkcionalita
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

@eel.expose
def list_remote_dir(path="."):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        ftp.cwd(path)
        items = []
        ftp.retrlines('LIST', lambda x: items.append(x))
        files = []

        for item in items:
            perms = item[0] if item else '-'
            splitted = item.split()
            name = splitted[-1] if len(splitted) >= 1 else '??'
            link_target = None
            is_symlink = False
            is_dir = False

            if perms == 'd':
                is_dir = True
            elif perms == 'l':
                is_symlink = True
                arrow_pos = item.find("->")
                if arrow_pos >= 0:
                    left_side = item[:arrow_pos].strip()
                    right_side = item[arrow_pos+2:].strip()
                    name = left_side.split()[-1] if left_side.split() else name
                    link_target = right_side
            else:
                is_dir = False

            files.append({
                "name": name,
                "is_dir": is_dir,
                "is_symlink": is_symlink,
                "link_target": link_target
            })
        return files
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

        file_items = []
        for name in os.listdir(abs_path):
            full_path = os.path.join(abs_path, name)
            file_items.append({
                "name": name,
                "is_dir": os.path.isdir(full_path)
            })
        return file_items
    except Exception as e:
        return f"Chyba: {str(e)}"

@eel.expose
def download_file(remote_file, local_file):
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        with open(local_file, 'wb') as f:
            ftp.retrbinary('RETR ' + remote_file, f.write)
        return "Súbor stiahnutý."
    except Exception as e:
        return f"Chyba: {str(e)}"

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
        return f"Chyba: {str(e)}"

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

            for f in files:
                local_file = os.path.join(root, f)
                remote_file = posixpath.join(remote_subdir, f)
                with open(local_file, 'rb') as file_obj:
                    ftp.storbinary(f'STOR {remote_file}', file_obj)

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

        items = []
        ftp.retrlines('LIST', lambda x: items.append(x))

        for item in items:
            perms = item[0] if item else '-'
            splitted = item.split()
            name = splitted[-1] if len(splitted) >= 1 else '??'
            if perms == 'd':
                sub_remote = posixpath.join(remote_folder, name)
                sub_local = os.path.join(local_folder, name)
                download_folder(sub_remote, sub_local)
            else:
                remote_file = posixpath.join(remote_folder, name)
                local_file = os.path.join(local_folder, name)
                with open(local_file, 'wb') as f:
                    ftp.retrbinary('RETR ' + remote_file, f.write)

        ftp.cwd(original_cwd)
        return "Priečinok stiahnutý."
    except Exception as e:
        return f"Chyba pri sťahovaní priečinka: {str(e)}"
    

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
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        # najprv skúsime zmazať ako súbor
        ftp.delete(path)
    except ftplib.error_perm:
        try:
            # ak nejde, pokúsime sa zmazať ako priečinok
            def ftp_recursive_delete(dir_path):
                try:
                    files = ftp.nlst(dir_path)
                except ftplib.error_perm:
                    files = []
                for f in files:
                    if f in ('.', '..'):
                        continue
                    try:
                        ftp.delete(f)
                    except ftplib.error_perm:
                        ftp_recursive_delete(f)
                ftp.rmd(dir_path)
            ftp_recursive_delete(path)
        except Exception as e:
            return f"Chyba pri mazaní priečinka na FTP: {str(e)}"
    except Exception as e:
        return f"Chyba pri mazaní súboru na FTP: {str(e)}"

    return "Vzdialená položka bola vymazaná."

@eel.expose
def rename_local_file(old_path, new_path):
    try:
        os.rename(old_path, new_path)
        return "Lokálny súbor/priečinok premenovaný."
    except Exception as e:
        return f"Chyba pri premenovaní lokálne: {str(e)}"

@eel.expose
def rename_remote_file(old_path, new_path):
    # Potrebujeme byť pripojení k FTP:
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
    """Vytvorí prázdny súbor, ak neexistuje."""
    try:
        if os.path.exists(path):
            return "Súbor už existuje."
        # Vytvor prázdny
        with open(path, 'w', encoding='utf-8'):
            pass
        return "Nový lokálny súbor vytvorený."
    except Exception as e:
        return f"Chyba pri vytváraní lokálneho súboru: {str(e)}"

@eel.expose
def create_remote_file(path):
    """Vytvorí prázdny súbor (STOR)."""
    global ftp
    if ftp is None:
        return "Nie si pripojený k FTP serveru."
    try:
        # `storbinary` s prázdnymi dátami:
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
###############################################################################
# NOVÉ: editor - načítanie/uloženie obsahu súboru
###############################################################################

@eel.expose
def read_file_content(path, is_remote):
    """Načíta obsah súboru ako text. Ak is_remote=True, stiahne z FTP."""
    if is_remote:
        global ftp
        if ftp is None:
            return "Chyba: Nie si pripojený k FTP serveru."
        # stiahnuť do pamäte
        mem = io.BytesIO()
        try:
            ftp.retrbinary('RETR ' + path, mem.write)
            data = mem.getvalue().decode('utf-8', errors='replace')
            return data
        except Exception as e:
            return f"Chyba pri čítaní remote: {str(e)}"
    else:
        # lokálne
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            return f"Chyba pri čítaní lokálne: {str(e)}"

@eel.expose
def save_file_content(path, is_remote, new_content):
    """Uloží text do daného súboru."""
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
    # Dôležité: použijeme block=False, aby sme mohli neskôr otvárať ďalšie okná
    eel.start('index.html', size=(1000, 600), block=True)
