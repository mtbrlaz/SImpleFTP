// V editor.html budeme očakávať parametre (cesta, remote boolean)
// ako Eel arguments. Ale Eel nemá priamo argumenty z CLI - urobíme to tak,
// že script.js pred spustením "editor.html" zavolá Eel cez "eel.start()"? 
// Jednoduchšie: pri otváraní okna použijeme parametre v URL #hash ?
//  -> editor.html#isremote|/cesta/k/suboru
//  Napr: editor.html?remote=0&path=C:/User/file.txt
//
// Ale Eel bohužiaľ neumožňuje takto out-of-box. 
// Jednoduchší prístup: Eel z script.js zavolá "eel.open_editor(path, isRemote)" v Pythone -> 
//   Python spraví eel.start('editor.html', block=False, port=...), 
//   a nejako povie parametre? 
// Pre jednoduchosť urobíme "global" v Pythone - "CURRENT_EDITOR_FILE"? 
//
// Tu, pre demonštráciu: script.js si do sessionStorage uloží parametre a editor.js si to prečíta.

let filePath = null;
let isRemote = false;

$(document).ready(function() {
    // Prečítame parametre z sessionStorage
    filePath = sessionStorage.getItem('editor_filePath');
    isRemote = (sessionStorage.getItem('editor_isRemote') === 'true');

    if (!filePath) {
        $('#filename').text('Neznámy');
        $('#editorArea').val('Chyba: Neviem, aký súbor otvoriť.');
        return;
    }
    $('#filename').text(filePath);

    // Zavoláme read_file_content
    eel.read_file_content(filePath, isRemote)((content) => {
        $('#editorArea').val(content);
    });
});

function saveFile() {
    let updated = $('#editorArea').val();
    eel.save_file_content(filePath, isRemote, updated)((resp) => {
        alert(resp);
    });
}

function closeWindow() {
    window.close(); 
}
