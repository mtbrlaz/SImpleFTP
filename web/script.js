////////////////////////////////////////////////////////////////////
// Globálne premenné
////////////////////////////////////////////////////////////////////

let currentLocalPath = '.';
let currentRemotePath = '.';

// root cesta (lokálna)
let localRootPath = '.';

// Zoznam položiek v paneloch
let localList = [];
let remoteList = [];

// Index vybranej položky
let localSelectedIndex = -1;
let remoteSelectedIndex = -1;

// Ktorý panel je aktívny: 'local' alebo 'remote'
let activePanel = 'local';

// Vybrané položky
let selectedLocalItem = null;
let selectedRemoteItem = null;

//kontext menu
let contextMenuTargetPanel = null;
let contextMenuItem = null;


////////////////////////////////////////////////////////////////////
// Kontextové menu
////////////////////////////////////////////////////////////////////

function getItemDetails(panel, index) {
    if (panel === 'local') {
        return localList[index];
    } else {
        return remoteList[index];
    }
}

$(document).ready(() => {
    highlightActivePanel();
    const contextMenu = $('#context-menu');
    
    // Pre oba panely
    $('#local-files, #remote-files').on('contextmenu', 'li', function(e) {
        e.preventDefault();
        contextMenuTargetPanel = $(this).parent().attr('id') === 'local-files' ? 'local' : 'remote';
        const index = $(this).index();
        
        // Aktualizujte vybranú položku
        if (contextMenuTargetPanel === 'local') {
            highlightLocalIndex(index);  // Táto funkcia nastaví selectedLocalItem
        } else {
            highlightRemoteIndex(index); // Táto funkcia nastaví selectedRemoteItem
        }
        
        contextMenuItem = getItemDetails(contextMenuTargetPanel, index);
        showContextMenu(e.pageX, e.pageY, true);
    });

    // Pravé kliknutie na prázdne miesto v paneli
    $('#local-files, #remote-files').on('contextmenu', function(e) {
        if ($(e.target).is('li')) return;
        e.preventDefault();
        contextMenuTargetPanel = $(this).attr('id') === 'local-files' ? 'local' : 'remote';
        contextMenuItem = null;
        showContextMenu(e.pageX, e.pageY, false);
    });

    // Skryť menu pri ľavom kliknutí
    $(document).click(() => contextMenu.addClass('hidden'));
});

function getItemDetails(panel, index) {
    return panel === 'local' ? 
        localList[index] : 
        remoteList[index];
}

function showContextMenu(x, y, isItem) {
    const menu = $('#context-menu');
    menu.removeClass('hidden')
        .css({ left: x + 'px', top: y + 'px' });

    // Skryť neplatné akcie
    menu.find('div').show();
    if (!isItem) {
        menu.find('div:not([onclick*="new_"])').hide();
    } else {
        menu.find('[onclick*="new_"]').hide();
        const item = contextMenuTargetPanel === 'local' ? selectedLocalItem : selectedRemoteItem;
        
        // Skryť "Zmazať" a "Premenovať" pre ".."
        if (item?.up) {
            menu.find('[onclick*="delete"], [onclick*="rename"]').hide();
        }
        
        // Skryť "Otvoriť" pre súbory (ak je potrebné)
        if (!item?.isDir) {
            menu.find('[onclick*="open"]').hide();
        }
    }
}

function handleContextAction(action) {
    if (!contextMenuTargetPanel) return;

    switch(action) {
        case 'open':
            handleEnter();
            break;
        case 'copy':
            handleF5();
            break;
        case 'rename':
            handleF2();
            break;
        case 'delete':
            handleDelete();
            break;
        case 'new_file':
            handleNewFile();
            break;
        case 'new_folder':
            handleF7();
            break;
    }
}

////////////////////////////////////////////////////////////////////
// Inicializácia
////////////////////////////////////////////////////////////////////

$(document).ready(() => {
    refreshLocalFiles(localRootPath);
    refreshRemoteFiles();

    // Kliknutie v lokálnom paneli
    $('#local-files').on('click', 'li', function() {
        setActivePanel('local');
        const index = $(this).index();
        highlightLocalIndex(index);
        highlightActivePanel();
        clearRemoteSelection();
    });

    // Kliknutie vo vzdialenom paneli
    $('#remote-files').on('click', 'li', function() {
        setActivePanel('remote');
        const index = $(this).index();
        highlightRemoteIndex(index);
        highlightActivePanel();
        clearLocalSelection();
    });

    // Ovládanie kláves
    $(document).keydown((e) => {
        // TAB
        if (e.key === 'Tab') {
            e.preventDefault();
            togglePanel();
            highlightActivePanel();
        } 
        // ENTER
        else if (e.key === 'Enter') {
            handleEnter();
        } 
        // F5 = kopírovanie
        else if (e.key === 'F5') {
            e.preventDefault();
            handleF5();
        }
        // F2 = premenovanie
        else if (e.key === 'F2') {
            e.preventDefault();
            handleF2();
        }
        // F7 = nový priečinok
        else if (e.key === 'F7') {
            e.preventDefault();
            handleF7();
        }
        // Shift+F4 = nový súbor
        else if (e.key === 'F4' && e.shiftKey) {
            e.preventDefault();
            handleNewFile();
        }
        // Delete = mazanie
        else if (e.key === 'Delete') {
            e.preventDefault();
            handleDelete();
        }
        // Pohyb
        else if (e.key === 'ArrowDown') {
            moveSelectionDown();
        } 
        else if (e.key === 'ArrowUp') {
            moveSelectionUp();
        }
    });
});


////////////////////////////////////////////////////////////////////
// Nastavenia - Modál (rootPath)
////////////////////////////////////////////////////////////////////

function openSettingsModal() {
    $('#rootPathInput').val(localRootPath);
    $('#settings-modal').show();
}

function closeSettingsModal() {
    $('#settings-modal').hide();
}

function saveSettings() {
    const newRoot = unifyPath($('#rootPathInput').val().trim());
    if (newRoot) {
        localRootPath = newRoot;
        currentLocalPath = localRootPath;
        refreshLocalFiles(localRootPath);
    }
    closeSettingsModal();
}


////////////////////////////////////////////////////////////////////
// FUNKCIE NAČÍTANIA
////////////////////////////////////////////////////////////////////

function refreshLocalFiles(path = '.') {
    path = unifyPath(path);
    eel.list_local_dir(path)((result) => {
        let localFiles = $('#local-files');
        localFiles.empty();

        if (typeof result === 'string') {
            alert(result);
            return;
        }

        localList = [];

        // ".." len ak nie sme v root
        if (path !== localRootPath) {
            localFiles.append(`<li data-up="true">🔼 ..</li>`);
            localList.push({ name: '..', is_dir: false, up: true });
        }

        result.forEach(file => {
            let icon = file.is_dir ? '📁' : '📄';
            localFiles.append(
                `<li data-name="${file.name}" data-dir="${file.is_dir}">
                   ${icon} ${file.name}
                </li>`
            );
            localList.push({
                name: file.name,
                is_dir: file.is_dir,
                up: false
            });
        });

        localSelectedIndex = localList.length > 0 ? 0 : -1;
        if (activePanel === 'local' && localSelectedIndex >= 0) {
            highlightLocalIndex(localSelectedIndex);
        } else {
            $('#local-files li').removeClass('bg-blue-100 font-semibold');
        }
    });
}

function refreshRemoteFiles(path = currentRemotePath) {
    eel.list_remote_dir(path)((result) => {
        let remoteFiles = $('#remote-files');
        remoteFiles.empty();

        if (typeof result === 'string') {
            alert(result);
            return;
        }

        remoteList = [];

        if (path !== '.') {
            remoteFiles.append(`<li data-up="true">🔼 ..</li>`);
            remoteList.push({ name: '..', is_dir: false, is_symlink: false, link_target: null, up: true });
        }

        result.forEach(item => {
            let icon = '📄';
            if (item.is_dir) icon = '📁';
            if (item.is_symlink) icon = '🔗';

            let displayName = item.name;
            if (item.is_symlink && item.link_target) {
                displayName += ` -> ${item.link_target}`;
            }

            remoteFiles.append(
                `<li data-name="${item.name}"
                     data-dir="${item.is_dir}"
                     data-symlink="${item.is_symlink}"
                     data-linktarget="${item.link_target || ''}">
                     ${icon} ${displayName}
                 </li>`
            );
            remoteList.push({
                name: item.name,
                is_dir: item.is_dir,
                is_symlink: item.is_symlink,
                link_target: item.link_target,
                up: false
            });
        });

        remoteSelectedIndex = remoteList.length > 0 ? 0 : -1;
        if (activePanel === 'remote' && remoteSelectedIndex >= 0) {
            highlightRemoteIndex(remoteSelectedIndex);
        } else {
            $('#remote-files li').removeClass('bg-blue-100 font-semibold');
        }
    });
}


////////////////////////////////////////////////////////////////////
// OVLÁDANIE VÝBERU - highlight, panel, pohyb...
////////////////////////////////////////////////////////////////////

function highlightActivePanel() {
    const localTitle = document.querySelector('#local-files').closest('div').querySelector('h2');
    const remoteTitle = document.querySelector('#remote-files').closest('div').querySelector('h2');

    [localTitle, remoteTitle].forEach(el => el.classList.remove('font-semibold', 'text-blue-600'));

    if (activePanel === 'local') {
        localTitle.classList.add('font-semibold', 'text-blue-600');
    } else {
        remoteTitle.classList.add('font-semibold', 'text-blue-600');
    }
}

function highlightLocalIndex(index) {
    localSelectedIndex = index;
    $('#local-files li').removeClass('bg-blue-100 font-semibold');
    let lis = $('#local-files li');
    if (index >= 0 && index < lis.length) {
        $(lis[index]).addClass('bg-blue-100 font-semibold');
        $(lis[index])[0].scrollIntoView({ block: 'nearest' });

        let liEl = $(lis[index]);
        selectedLocalItem = {
            name: liEl.data('name'),
            isDir: (liEl.data('dir') === true || liEl.data('dir') === 'true'),
            up: !!liEl.data('up')
        };
    } else {
        selectedLocalItem = null;
    }
}

function highlightRemoteIndex(index) {
    remoteSelectedIndex = index;
    $('#remote-files li').removeClass('bg-blue-100 font-semibold');
    let lis = $('#remote-files li');
    if (index >= 0 && index < lis.length) {
        $(lis[index]).addClass('bg-blue-100 font-semibold');
        $(lis[index])[0].scrollIntoView({ block: 'nearest' });

        let liEl = $(lis[index]);
        selectedRemoteItem = {
            name: liEl.data('name'),
            isDir: (liEl.data('dir') === true || liEl.data('dir') === 'true'),
            isSymlink: (liEl.data('symlink') === true || liEl.data('symlink') === 'true'),
            linkTarget: liEl.data('linktarget'),
            up: !!liEl.data('up')
        };
    } else {
        selectedRemoteItem = null;
    }
}

function setActivePanel(panel) {
    activePanel = panel;
}

function togglePanel() {
    if (activePanel === 'local') {
        setActivePanel('remote');
        if (remoteSelectedIndex >= 0) highlightRemoteIndex(remoteSelectedIndex);
        //highlightLocalIndex(-1);
    } else {
        setActivePanel('local');
        if (localSelectedIndex >= 0) highlightLocalIndex(localSelectedIndex);
        //highlightRemoteIndex(-1);
    }
}

function moveSelectionDown() {
    if (activePanel === 'local') {
        if (localList.length < 1) return;
        let newIndex = localSelectedIndex + 1;
        if (newIndex >= localList.length) newIndex = 0;
        highlightLocalIndex(newIndex);
    } else {
        if (remoteList.length < 1) return;
        let newIndex = remoteSelectedIndex + 1;
        if (newIndex >= remoteList.length) newIndex = 0;
        highlightRemoteIndex(newIndex);
    }
}

function moveSelectionUp() {
    if (activePanel === 'local') {
        if (localList.length < 1) return;
        let newIndex = localSelectedIndex - 1;
        if (newIndex < 0) newIndex = localList.length - 1;
        highlightLocalIndex(newIndex);
    } else {
        if (remoteList.length < 1) return;
        let newIndex = remoteSelectedIndex - 1;
        if (newIndex < 0) newIndex = remoteList.length - 1;
        highlightRemoteIndex(newIndex);
    }
}

function clearLocalSelection() {
    selectedLocalItem = null;
    localSelectedIndex = -1;
    $('#local-files li').removeClass('bg-blue-100 font-semibold');
}

function clearRemoteSelection() {
    selectedRemoteItem = null;
    remoteSelectedIndex = -1;
    $('#remote-files li').removeClass('bg-blue-100 font-semibold');
}


////////////////////////////////////////////////////////////////////
// ZÁKLADNÉ AKCIE
////////////////////////////////////////////////////////////////////

function connect() {
    const protocol = $('#protocol').val();
    const host = $('#host').val();
    const port = $('#port').val();
    const username = $('#username').val();
    const password = $('#password').val();

    eel.connect_to_server(host, username, password, protocol, port)((response) => {
        alert(response);
        currentRemotePath = '.';
        refreshRemoteFiles();
    });
}

// Enter = navigácia do priečinka / symlink / open file editor
function handleEnter() {
    if (activePanel === 'local' && selectedLocalItem) {
        if (selectedLocalItem.up) {
            if (currentLocalPath !== localRootPath) {
                currentLocalPath = osPathUp(currentLocalPath) || localRootPath;
                refreshLocalFiles(currentLocalPath);
            }
        } else if (selectedLocalItem.isDir) {
            if (currentLocalPath === '.') {
                currentLocalPath = selectedLocalItem.name;
            } else {
                currentLocalPath = unifyPath(currentLocalPath + '/' + selectedLocalItem.name);
            }
            refreshLocalFiles(currentLocalPath);
        } else {
            // Obyčajný súbor -> otvor editor
            let filePath = (currentLocalPath === '.')
                ? selectedLocalItem.name
                : unifyPath(currentLocalPath + '/' + selectedLocalItem.name);
            openEditor(filePath, false);
        }
    }
    else if (activePanel === 'remote' && selectedRemoteItem) {
        if (selectedRemoteItem.up) {
            if (currentRemotePath !== '.') {
                currentRemotePath = ftpPathUp(currentRemotePath) || '.';
                refreshRemoteFiles(currentRemotePath);
            }
        } else if (selectedRemoteItem.isSymlink) {
            let linkT = selectedRemoteItem.linkTarget;
            if (linkT) {
                currentRemotePath = linkT;
                refreshRemoteFiles(currentRemotePath);
            } else {
                alert("Symlink bez cieľa!");
            }
        } else if (selectedRemoteItem.isDir) {
            if (currentRemotePath === '.') {
                currentRemotePath = '/' + selectedRemoteItem.name;
            } else {
                currentRemotePath += '/' + selectedRemoteItem.name;
            }
            refreshRemoteFiles(currentRemotePath);
        } else {
            // Súbor -> editor
            let filePath = (currentRemotePath === '.')
                ? selectedRemoteItem.name
                : (currentRemotePath + '/' + selectedRemoteItem.name);
            openEditor(filePath, true);
        }
    }
}

// F5 = kopírovanie
function handleF5() {
    if (activePanel === 'local' && selectedLocalItem) {
        if (selectedLocalItem.up) {
            alert('Nie je možné kopírovať ".."');
            return;
        }
        let localFull = (currentLocalPath === '.')
            ? selectedLocalItem.name
            : unifyPath(currentLocalPath + '/' + selectedLocalItem.name);
        if (selectedLocalItem.isDir) {
            let remoteTarget = prompt("Zadaj cieľovú cestu na FTP:", selectedLocalItem.name);
            if (remoteTarget) {
                eel.upload_folder(localFull, remoteTarget)((resp) => {
                    alert(resp);
                    refreshRemoteFiles();
                });
            }
        } else {
            let remoteFile = prompt("Zadaj cieľovú cestu súboru na FTP:", selectedLocalItem.name);
            if (remoteFile) {
                eel.upload_file(localFull, remoteFile)((resp) => {
                    alert(resp);
                    refreshRemoteFiles();
                });
            }
        }
    }
    else if (activePanel === 'remote' && selectedRemoteItem) {
        if (selectedRemoteItem.up) {
            alert('Nie je možné kopírovať ".."');
            return;
        }
        let remoteFull = (currentRemotePath === '.')
            ? selectedRemoteItem.name
            : (currentRemotePath + '/' + selectedRemoteItem.name);

        if (selectedRemoteItem.isDir) {
            let localTarget = prompt("Zadaj lokálnu cieľovú cestu:", selectedRemoteItem.name);
            if (localTarget) {
                eel.download_folder(remoteFull, localTarget)((resp) => {
                    alert(resp);
                    refreshLocalFiles();
                });
            }
        } else {
            let localFile = prompt("Zadaj lokálnu cieľovú cestu súboru:", selectedRemoteItem.name);
            if (localFile) {
                eel.download_file(remoteFull, localFile)((resp) => {
                    alert(resp);
                    refreshLocalFiles();
                });
            }
        }
    }
}

// F2 = rename
function handleF2() {
    if (activePanel === 'local' && selectedLocalItem) {
        if (selectedLocalItem.up) {
            alert('Nemožno premenovať ".."');
            return;
        }
        let oldName = (currentLocalPath === '.')
            ? selectedLocalItem.name
            : unifyPath(currentLocalPath + '/' + selectedLocalItem.name);

        let newName = prompt("Zadaj nový názov:", selectedLocalItem.name);
        if (!newName) return;

        let fullNew = (currentLocalPath === '.')
            ? newName
            : unifyPath(currentLocalPath + '/' + newName);

        eel.rename_local_file(oldName, fullNew)((resp) => {
            alert(resp);
            refreshLocalFiles(currentLocalPath);
        });
    }
    else if (activePanel === 'remote' && selectedRemoteItem) {
        if (selectedRemoteItem.up) {
            alert('Nemožno premenovať ".."');
            return;
        }
        let oldName = (currentRemotePath === '.')
            ? selectedRemoteItem.name
            : (currentRemotePath + '/' + selectedRemoteItem.name);

        let newName = prompt("Zadaj nový názov:", selectedRemoteItem.name);
        if (!newName) return;

        let fullNew = (currentRemotePath === '.')
            ? newName
            : (currentRemotePath + '/' + newName);

        eel.rename_remote_file(oldName, fullNew)((resp) => {
            alert(resp);
            refreshRemoteFiles(currentRemotePath);
        });
    }
}

// Shift+F4 = nový súbor
function handleNewFile() {
    let name = prompt("Zadaj názov nového súboru:");
    if (!name) return;

    if (activePanel === 'local') {
        let fullPath = (currentLocalPath === '.')
            ? name
            : unifyPath(currentLocalPath + '/' + name);

        eel.create_local_file(fullPath)((resp) => {
            alert(resp);
            refreshLocalFiles(currentLocalPath);
        });
    }
    else if (activePanel === 'remote') {
        let fullPath = (currentRemotePath === '.')
            ? name
            : (currentRemotePath + '/' + name);

        eel.create_remote_file(fullPath)((resp) => {
            alert(resp);
            refreshRemoteFiles(currentRemotePath);
        });
    }
}

// F7 = nový priečinok
function handleF7() {
    let name = prompt("Zadaj názov nového priečinka:");
    if (!name) return;

    if (activePanel === 'local') {
        let fullPath = (currentLocalPath === '.')
            ? name
            : unifyPath(currentLocalPath + '/' + name);

        eel.create_local_folder(fullPath)((resp) => {
            alert(resp);
            refreshLocalFiles(currentLocalPath);
        });
    }
    else if (activePanel === 'remote') {
        let fullPath = (currentRemotePath === '.')
            ? name
            : (currentRemotePath + '/' + name);

        eel.create_remote_folder(fullPath)((resp) => {
            alert(resp);
            refreshRemoteFiles(currentRemotePath);
        });
    }
}

// Delete = mazanie
function handleDelete() {
    let confirmDelete = confirm("Naozaj chceš vymazať označenú položku?");
    if (!confirmDelete) return;

    if (activePanel === 'local' && selectedLocalItem) {
        if (selectedLocalItem.up) {
            alert('Nemôžeš zmazať ".."');
            return;
        }

        let localFull = (currentLocalPath === '.')
            ? selectedLocalItem.name
            : unifyPath(currentLocalPath + '/' + selectedLocalItem.name);

        eel.delete_local(localFull)((resp) => {
            alert(resp);
            refreshLocalFiles(currentLocalPath);
        });
    }
    else if (activePanel === 'remote' && selectedRemoteItem) {
        if (selectedRemoteItem.up) {
            alert('Nemôžeš zmazať ".."');
            return;
        }

        let remoteFull = (currentRemotePath === '.')
            ? selectedRemoteItem.name
            : (currentRemotePath + '/' + selectedRemoteItem.name);

        eel.delete_remote(remoteFull)((resp) => {
            alert(resp);
            refreshRemoteFiles(currentRemotePath);
        });
    }
}


////////////////////////////////////////////////////////////////////
// Editor: Otvorenie nového okna so sessionStorage parametrami
////////////////////////////////////////////////////////////////////

function openEditor(filePath, isRemote) {
    sessionStorage.setItem('editor_filePath', filePath);
    sessionStorage.setItem('editor_isRemote', isRemote ? 'true' : 'false');

    window.open('editor.html', '_blank', 'width=800,height=600');
}


////////////////////////////////////////////////////////////////////
// POMOCNÉ FUNKCIE
////////////////////////////////////////////////////////////////////

function unifyPath(path) {
    return path.replace(/\\/g, '/');
}

function osPathUp(path) {
    path = unifyPath(path);
    const parts = path.split('/');
    parts.pop();
    return parts.join('/');
}

function ftpPathUp(path) {
    const parts = path.split('/').filter(p => p !== '' && p !== '.');
    parts.pop();
    if (parts.length === 0) {
        return '.';
    } else {
        return parts.join('/');
    }
}


////////////////////////////////////////////////////////////////////
// ACCESS MANAGER pre WinSCP Sessions
////////////////////////////////////////////////////////////////////

function openAccessManager() {
    $('#access-manager-modal').show();
    loadSessions();
}

function closeAccessManager() {
    $('#access-manager-modal').hide();
}

function loadSessions() {
    eel.load_winscp_sessions()((sessions) => {
        let list = $('#am-session-list');
        list.empty();
        sessions.forEach(sess => {
            const li = $(`
                <li>
                  <b>${sess.session_name}</b>
                  (host=${sess.host}, user=${sess.user})
                  <button class="bg-green-500 text-white px-4 py-2 rounded hover:bg-red-600 mt-4" onclick="useSession('${sess.session_name}')">Použiť</button>
                  <button class="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 mt-4" onclick="removeSession('${sess.session_name}')">X</button>
                </li>
            `);
            list.append(li);
        });
    });
}


function addSession() {
    let sessionName = $('#am-session-name').val().trim();
    let host = $('#am-host').val().trim();
    let user = $('#am-user').val().trim();
    let password = $('#am-password').val().trim();
    let protocol = $('#am-protocol').val();
    let port = $('#am-port').val();

    if (!sessionName || !host || !user) {
        alert("Vyplň aspoň Session Name, Host a User");
        return;
    }
    eel.add_winscp_session(host, user, password, sessionName, protocol, port)((resp) => {
        alert(resp);
        loadSessions();
    });
}

function useSession(sessionName) {
    eel.load_winscp_sessions()((sessions) => {
        let s = sessions.find(x => x.session_name === sessionName);
        if (!s) {
            alert("Session sa nenašla");
            return;
        }
        $('#protocol').val(s.protocol);
        $('#host').val(s.host);
        $('#port').val(s.port);
        $('#username').val(s.user);
        $('#password').val(s.password);
        closeAccessManager();
    });
}
