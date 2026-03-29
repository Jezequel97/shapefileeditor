console.log("JS VERSION 10.3 LOADED")

let hot = null;
let headers = [];

const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

function getColumnLetter(index) {
    let result = "";
    let n = index + 1;

    while (n > 0) {
        const remainder = (n - 1) % 26;
        result = alphabet[remainder] + result;
        n = Math.floor((n - 1) / 26);
    }

    return result;
}

function updateFormulaBar(row, col) {
    document.getElementById("cellRef").textContent =
        `${getColumnLetter(col)}${row + 1}`;

    const value = hot.getDataAtCell(row, col) ?? "";
    document.getElementById("formulaInput").value = value;
}

async function loadShapefile() {
    const file = document.getElementById("fileInput").files[0];

    if (!file) {
        alert("Kies eerst een ZIP-bestand met een shapefile.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload-table", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        headers = data.columns.map(col => col.field);

        const rows = [
			[...headers],
			...data.rows.map(row =>
				headers.map(h => row[h] ?? "")
			)
		];

        const container = document.getElementById("table");

        if (hot) {
            hot.destroy();
        }

        hot = new Handsontable(container, {
            data: rows,

            rowHeaders: true,
            colHeaders: true,
			
			fixedRowsTop: 1,

            width: "100%",
            height: 600,
			
			rowHeights: 37,
			autoRowSize: false,

            licenseKey: "non-commercial-and-evaluation",

            manualColumnResize: true,
            manualRowResize: true,

            autoColumnSize: {
                useHeaders: true
            },

            autoRowSize: true,

            stretchH: "none",
            wordWrap: false,

            renderAllRows: true,

            contextMenu: true,
            copyPaste: true,
            fillHandle: true,
            undo: true,

            // Excel-achtige navigatie
            enterMoves: { row: 1, col: 0 },
            tabMoves: { row: 0, col: 1 },

            cells(row, col) {
                const props = { type: "text" };

                if (row === 0) {
                    props.className = "shape-header";
                }

                return props;
            },

            afterSelection(row, col) {
                updateFormulaBar(row, col);
            },

            afterBeginEditing(row, col) {
                updateFormulaBar(row, col);

                const editor = hot.getActiveEditor();
                if (!editor) return;

                const input = editor.TEXTAREA || editor.TEXTAREA_PARENT?.querySelector("textarea");
                if (!input) return;

                // live sync cel → formulebalk
                input.addEventListener("input", () => {
                    document.getElementById("formulaInput").value = input.value;
                });
            },

            afterChange(changes, source) {
                if (!changes || source === "loadData") return;

                const selected = hot.getSelectedLast();
                if (!selected) return;

                const [row, col] = selected;
                updateFormulaBar(row, col);
            },

            // Excel keyboard gedrag
            beforeKeyDown(e) {
                const selected = hot.getSelectedLast();
                if (!selected) return;

                const [row, col] = selected;

                // F2 = edit cel
                if (e.key === "F2") {
                    e.stopImmediatePropagation();
                    hot.selectCell(row, col);
                    hot.getActiveEditor()?.beginEditing();
                }

                // Shift+Enter = omhoog
                if (e.key === "Enter" && e.shiftKey) {
                    e.stopImmediatePropagation();
                    hot.selectCell(Math.max(row - 1, 0), col);
                }

                // Ctrl+D = waarde naar beneden kopiëren
                if (e.ctrlKey && e.key.toLowerCase() === "d") {
                    e.preventDefault();
                    const sel = hot.getSelected();
                    if (!sel) return;

                    const [r1, c1, r2, c2] = sel[0];
                    const value = hot.getDataAtCell(r1, c1);

                    for (let r = r1 + 1; r <= r2; r++) {
                        hot.setDataAtCell(r, c1, value, "fill");
                    }
                }
            },

            // dubbelklik kolomrand = auto-resize zoals Excel
            afterGetColHeader(col, TH) {
                TH.ondblclick = () => {
                    hot.getPlugin("autoColumnSize").recalculateAllColumnsWidth();
                    hot.render();
                };
            },

            // Ctrl+Enter = schrijf waarde naar hele selectie
            beforeKeyDown(e) {
                const selected = hot.getSelectedLast();
                if (!selected) return;

                const [row, col] = selected;

                if (e.key === "F2") {
                    e.stopImmediatePropagation();
                    hot.selectCell(row, col);
                    hot.getActiveEditor()?.beginEditing();
                }

                if (e.key === "Enter" && e.shiftKey) {
                    e.stopImmediatePropagation();
                    hot.selectCell(Math.max(row - 1, 0), col);
                }

                if (e.ctrlKey && e.key === "Enter") {
                    e.preventDefault();

                    const selection = hot.getSelected();
                    if (!selection) return;

                    const [r1, c1, r2, c2] = selection[0];
                    const value = hot.getDataAtCell(row, col);

                    for (let r = Math.min(r1, r2); r <= Math.max(r1, r2); r++) {
                        for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c++) {
                            hot.setDataAtCell(r, c, value, "bulkFill");
                        }
                    }
                }
            }
        });

        // type detectie voor shapefile kolommen
        const detectedTypes = headers.map((header, index) => {
            const sample = data.rows
                .map(r => r[header])
                .find(v => v !== null && v !== undefined && v !== "");

            if (typeof sample === "number") {
                return Number.isInteger(sample) ? "int" : "float";
            }

            return "string";
        });

        console.log("Detected column types:", detectedTypes);

        /* simpele filterbalk toevoegen boven de tabel
        const existingFilter = document.getElementById("columnFilter");
        if (existingFilter) existingFilter.remove();

        const filterInput = document.createElement("input");
        filterInput.id = "columnFilter";
        filterInput.placeholder = "Filter geselecteerde kolom...";
        filterInput.style.marginBottom = "10px";
        filterInput.style.padding = "8px 12px";
        filterInput.style.width = "260px";

        container.parentNode.insertBefore(filterInput, container);

        filterInput.addEventListener("input", () => {
            const selected = hot.getSelectedLast();
            if (!selected) return;

            const [, col] = selected;
            const search = filterInput.value.toLowerCase();

            hot.loadData(rows.filter((row, index) => {
                if (index === 0) return true;
                return String(row[col] ?? "").toLowerCase().includes(search);
            }));
        });*/
    } catch (err) {
        console.error(err);
        alert("Er ging iets fout bij het laden van de shapefile.");
    }
}

// formulebalk → cel sync

document.getElementById("formulaInput").addEventListener("input", function () {
    if (!hot) return;

    const selected = hot.getSelectedLast();
    if (!selected) return;

    const [row, col] = selected;

    const editor = hot.getActiveEditor();

    if (editor && editor.isOpened()) {
        const input = editor.TEXTAREA;
        if (input && input.value !== this.value) {
            input.value = this.value;
        }
    }

    hot.setDataAtCell(row, col, this.value, "formula");
});

async function saveChanges() {
    if (!hot) {
        alert("Laad eerst een shapefile.");
        return;
    }

    try {
        const tableData = hot.getData();

        const newHeaders = tableData[0];
		console.log("newHeaders", newHeaders);
        const dataRows = tableData.slice(1);
		
		 // bepaal welke kolommen hernoemd zijn
        const renameMap = {};

        headers.forEach((oldName, index) => {
            const newName = newHeaders[index];

            if (oldName !== newName && newName.trim() !== "") {
                renameMap[oldName] = newName.trim();
				console.log("renameMap", renameMap);
            }
        });

        const rows = dataRows.map(row => {
            const obj = {};

            newHeaders.forEach((header, index) => {
                obj[header] = row[index];
            });

            return obj;
        });

        const response = await fetch("/edit-table", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
				rename: renameMap,
				rows
			})
        });

        const result = await response.json();

        if (result.error) {
            alert(result.error);
            return;
        }

        alert("Wijzigingen opgeslagen.");
    } catch (err) {
        console.error(err);
        alert("Er ging iets fout bij het opslaan.");
    }
}

function downloadShapefile() {
    window.location.href = "/download";
}

document.getElementById("loadBtn").addEventListener("click", loadShapefile);
document.getElementById("saveBtn").addEventListener("click", saveChanges);
document.getElementById("downloadBtn").addEventListener("click", downloadShapefile);