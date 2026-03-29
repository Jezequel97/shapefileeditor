console.log("JS VERSION 7 LOADED")

let activeColumns = []
let hiddenColumns = []
let types = {}
let originalColumns = []


// 📤 Upload shapefile
async function upload() {
    const file = document.getElementById("fileInput").files[0]

    if (!file) {
        alert("Select a ZIP file first")
        return
    }

    const formData = new FormData()
    formData.append("file", file)

    const res = await fetch("/upload", {
        method: "POST",
        body: formData
    })

    const data = await res.json()

    if (data.error) {
        alert(data.error)
        return
    }

    originalColumns = [...data.columns]
    activeColumns = [...data.columns]
    hiddenColumns = []
    types = data.types

	clearPreview()
    render()
	renderPreview(data.preview, data.columns)
}


// 🧱 Maak kolom item
function createItem(col) {
    const div = document.createElement("div")
    div.className = "item"

    // 🔥 highlight nieuwe kolommen
    if (!originalColumns.includes(col)) {
        div.classList.add("new-column")
    }

    const input = document.createElement("input")
    input.value = col
    input.dataset.original = col

    const typeLabel = document.createElement("small")
    typeLabel.innerText = types[col] || "string"

    div.appendChild(input)
    div.appendChild(document.createElement("br"))
    div.appendChild(typeLabel)

    return div
}


// 🎨 Render UI
function render() {
    const active = document.getElementById("active")
    const hidden = document.getElementById("hidden")
	
	if (window.activeSortable) window.activeSortable.destroy()
	if (window.hiddenSortable) window.hiddenSortable.destroy()

    active.innerHTML = ""
    hidden.innerHTML = ""

    activeColumns.forEach(col => active.appendChild(createItem(col)))
    hiddenColumns.forEach(col => hidden.appendChild(createItem(col)))

    // 🔥 drag overal behalve input
    window.activeSortable = new Sortable(active, {
        group: "columns",
        animation: 150,
        filter: "input",
        preventOnFilter: false,
        onEnd: updateState
    })

    window.hiddenSortable = new Sortable(hidden, {
        group: "columns",
        animation: 150,
        filter: "input",
        preventOnFilter: false,
        onEnd: updateState
    })
}

function renderPreview(preview, columns) {

    
	const container = document.getElementById("previewTable")
    const table = container.querySelector("table")
	const placeholder = document.getElementById("previewPlaceholder")
	
	// 🔥 Preview
    if (!preview || preview.length === 0) {
        table.innerHTML = ""
        if (placeholder) placeholder.style.display = "block"
        return
    }
	
	// 🔥 verberg placeholder
    if (placeholder) {
        placeholder.style.display = "none"
    }

    // 🔥 reset (ESSENTIEEL)
    table.innerHTML = ""

    // 🔹 header
    const header = document.createElement("tr")

    columns.forEach(col => {
        const th = document.createElement("th")
        th.innerText = col
        header.appendChild(th)
    })

    table.appendChild(header)

    // 🔹 rows
    preview.forEach(row => {
        const tr = document.createElement("tr")

        columns.forEach(col => {
            const td = document.createElement("td")
            td.innerText = formatCell(row[col])
            tr.appendChild(td)
        })

        table.appendChild(tr)
    })
}

function formatCell(value) {
    if (value === null || value === undefined) return ""

    const str = String(value)

    if (str.length > 20) {
        return str.substring(0, 20) + "..."
    }

    return str
}

function clearPreview() {
    const container = document.getElementById("previewTable")
    const table = container.querySelector("table")
    const placeholder = document.getElementById("previewPlaceholder")

    table.innerHTML = ""
    placeholder.style.display = "block"
}

// 🔄 Sync state na drag
function updateState() {
    const active = document.getElementById("active")
    const hidden = document.getElementById("hidden")

    activeColumns = Array.from(active.children).map(el =>
        el.querySelector("input").value
    )

    hiddenColumns = Array.from(hidden.children).map(el =>
        el.querySelector("input").value
    )
}


// ➕ Kolom toevoegen (nieuwe UI)
function addColumn() {
    const nameInput = document.getElementById("newName")
    const typeInput = document.getElementById("newType")
	const defaultInput = document.getElementById("newDefault")

    const name = nameInput.value.trim()
    const type = typeInput.value
	const defaultValue = defaultInput.value

    if (!name) {
        alert("Column name required")
        return
    }

    if (activeColumns.includes(name) || hiddenColumns.includes(name)) {
        alert("Column already exists")
        return
    }

    activeColumns.unshift(name)
    types[name] = type || "string"
	
	if (!window.defaults) window.defaults = {}
	window.defaults[name] = defaultValue

    // 🔥 reset input
    nameInput.value = ""
	defaultInput.value = ""

    render()
}

// 🚀 Apply changes naar backend
async function applyChanges() {

    const active = document.getElementById("active")
    const hidden = document.getElementById("hidden")

    const rename = {}
    const newActiveColumns = []

    // 🔥 rename + volgorde
    Array.from(active.children).forEach(el => {
        const input = el.querySelector("input")

        const original = input.dataset.original
        const current = input.value

        newActiveColumns.push(current)

        if (original !== current) {
            rename[original] = current
        }
    })

    activeColumns = newActiveColumns

    // 🔥 delete
    const deleteCols = Array.from(hidden.children).map(el =>
        el.querySelector("input").value
    )

    // 🔥 rename targets
    const renamedTargets = Object.values(rename)

    // 🔥 add
    const add = {}

    activeColumns.forEach(col => {
        if (
            !originalColumns.includes(col) &&
            !renamedTargets.includes(col)
        ) {
            add[col] = {
                type: types[col] || "string",
                default: window.defaults?.[col] || ""
            }
        }
    })

    console.log("RENAME:", rename)
    console.log("DELETE:", deleteCols)
    console.log("ADD:", add)
    console.log("ORDER:", activeColumns)

    const res = await fetch("/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            rename: rename,
            delete: deleteCols,
            order: activeColumns,
            add: add
        })
    })

    const data = await res.json()
	renderPreview(data.preview, data.columns)

    if (data.error) {
        alert(data.error)
        return
    }

    // 🔄 update state
    activeColumns = data.columns
    hiddenColumns = []
    types = data.types

    render()
}

// 📥 Download shapefile
function download() {
    window.location.href = "/download"
}


// ⌨️ Enter = add column
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("newName")

    if (input) {
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                addColumn()
            }
        })
    }
})