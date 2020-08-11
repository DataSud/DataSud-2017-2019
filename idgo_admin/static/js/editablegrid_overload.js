EditableGrid.prototype._rendergrid = function(containerid, className, tableid) {
	with (this) {

		lastSelectedRowIndex = -1;
		_currentPageIndex = getCurrentPageIndex();

		// if we are already attached to an existing table, just update the cell contents
		if (typeof table != "undefined" && table != null) {

			var _data = dataUnfiltered == null ? data : dataUnfiltered;

			// render headers
			_renderHeaders();

			// render content
			var rows = tBody.rows;
			var skipped = 0;
			var displayed = 0;
			var rowIndex = 0;

			for (var i = 0; i < rows.length; i++) {
				// filtering and pagination in attach mode means hiding rows
				if (!_data[i].visible || (pageSize > 0 && displayed >= pageSize)) {
					if (rows[i].style.display != 'none') {
						rows[i].style.display = 'none';
						rows[i].hidden_by_editablegrid = true;
					};
				} else {
					if (skipped < pageSize * _currentPageIndex) {
						skipped++;
						if (rows[i].style.display != 'none') {
							rows[i].style.display = 'none';
							rows[i].hidden_by_editablegrid = true;
						};
					} else {
						displayed++;
						var cols = rows[i].cells;
						if (typeof rows[i].hidden_by_editablegrid != 'undefined' && rows[i].hidden_by_editablegrid) {
							rows[i].style.display = '';
							rows[i].hidden_by_editablegrid = false;
						};
						rows[i].rowId = getRowId(rowIndex);
						rows[i].id = _getRowDOMId(rows[i].rowId);
						for (var j = 0; j < cols.length && j < columns.length; j++) {
							if (columns[j].renderable) {
								columns[j].cellRenderer._render(rowIndex, j, cols[j], getValueAt(rowIndex, j));
							};
						};
					};
					rowIndex++;
				};
			};

			// attach handler on click or double click
			table.editablegrid = this;
			if (doubleclick) table.ondblclick = function(e) {
				this.editablegrid.mouseClicked(e);
			};
			else table.onclick = function(e) {
				this.editablegrid.mouseClicked(e);
			};

		} else { // we must render a whole new table

			if (!containerid) {
				return console.error("Container ID not specified (renderGrid not called yet ?)");
			};
			if (!_$(containerid)) {
				return console.error("Unable to get element [" + containerid + "]");
			};

			currentContainerid = containerid;
			currentClassName = className;
			currentTableid = tableid;

			var startRowIndex = 0;
			var endRowIndex = getRowCount();

			// paginate if required
			if (pageSize > 0) {
				startRowIndex = _currentPageIndex * pageSize;
				endRowIndex = Math.min(getRowCount(), startRowIndex + pageSize);
			};

			// create editablegrid table and add it to our container
			this.table = document.createElement("table");
			table.className = className || "editablegrid";
			if (typeof tableid != "undefined") {
				table.id = tableid;
			};
			while (_$(containerid).hasChildNodes()) _$(containerid).removeChild(_$(containerid).firstChild);
			_$(containerid).appendChild(table);

			// create header
			if (caption) {
				var captionElement = document.createElement("CAPTION");
				captionElement.innerHTML = this.caption;
				table.appendChild(captionElement);
			};

			this.tHead = document.createElement("THEAD");
			table.appendChild(tHead);
			var trHeader = tHead.insertRow(0);
			var columnCount = getColumnCount();
			var newcolumnCount = getColumnCount(); //new
			for (var c = 0; c < columnCount; c++) {
				if (columns[c].label === "_HIDDEN") { //new
					newcolumnCount--; //new
					continue; //new
				}; //new
				var headerCell = document.createElement("TH");
				var td = trHeader.appendChild(headerCell);
				columns[c].headerRenderer._render(-1, c, td, columns[c].label);
			};

			// create body and rows
			this.tBody = document.createElement("TBODY");
			table.appendChild(tBody);
			var insertRowIndex = 0;
			for (var i = startRowIndex; i < endRowIndex; i++) {
				var tr = tBody.insertRow(insertRowIndex++);
				tr.rowId = data[i]['id'];
				tr.id = this._getRowDOMId(data[i]['id']);
				for (j = 0; j < newcolumnCount; j++) { //new (edited)
					// create cell and render its content
					var td = tr.insertCell(j);
					columns[j].cellRenderer._render(i, j, td, getValueAt(i, j));
				};
			};

			// attach handler on click or double click
			_$(containerid).editablegrid = this;
			if (doubleclick) _$(containerid).ondblclick = function(e) {
				this.editablegrid.mouseClicked(e);
			};
			else _$(containerid).onclick = function(e) {
				this.editablegrid.mouseClicked(e);
			};
		};

		// callback
		tableRendered(containerid, className, tableid);
	};

};

EditableGrid.prototype.editCell = function(rowIndex, columnIndex) {
	var target = this.getCell(rowIndex, columnIndex);
	with (this) {
		var column = columns[columnIndex];
		if (column) {
			// if another row has been selected: callback
			if (rowIndex > -1) {
				rowSelected(lastSelectedRowIndex, rowIndex);
				if (lastSelectedRowIndex == rowIndex) {
					lastSelectedRowIndex = -1;
				} else {
					lastSelectedRowIndex = rowIndex;
				};
			};
			// edit current cell value
			if (!column.editable) {
				readonlyWarning(column);
			} else {
				if (rowIndex < 0) {
					if (column.headerEditor && isHeaderEditable(rowIndex, columnIndex))
					column.headerEditor.edit(rowIndex, columnIndex, target, column.label);
				} else if (column.cellEditor && isEditable(rowIndex, columnIndex))
				column.cellEditor.edit(rowIndex, columnIndex, target, getValueAt(rowIndex, columnIndex));
			};
		};
	};
};

EditableGrid.prototype.updatePaginator = function(grid) {

	var paginator = $('#' + this.currentContainerid + '-paginator').empty();
	var navigator = paginator.parent().hide();
	var pageCount = this.getPageCount();

	var interval = this.getSlidingPageInterval(9);
	if (interval == null) {
		return;
	};
	navigator.show();

	var pages = this.getPagesInInterval(interval, function(pageIndex, isCurrent) {
		var pageLink = $('<li>').html('<a href="#">' + (pageIndex + 1) + '</a>');
		if (isCurrent) {
			return pageLink.addClass('active');
		};
		return pageLink.click(function(e) {
			e.stopPropagation();
			grid.setPageIndex(parseInt(e.currentTarget.innerText) - 1);
			e.preventDefault();
		});
	});

	var firstLink = $('<li>').html('<a href="#" aria-label="First page"><span class="glyphicon glyphicon-fast-backward" aria-hidden="true"></span></a>');
	if (!this.canGoBack()) {
		firstLink.addClass('disabled');
	} else {
		firstLink.click(function(e) {
			e.stopPropagation();
			grid.firstPage();
			e.preventDefault();
		});
	};
	paginator.append(firstLink);

	var prevLink = $('<li>').html('<a href="#" aria-label="Previous page"><span class="glyphicon glyphicon-backward" aria-hidden="true"></span></a>');
	if (!this.canGoBack()) {
		prevLink.addClass('disabled');
	} else {
		prevLink.click(function(e) {
			e.stopPropagation();
			grid.prevPage();
			e.preventDefault();
		});
	};
	paginator.append(prevLink);

	for (p = 0; p < pages.length; p++) {
		paginator.append(pages[p]);
	};

	var nextLink = $('<li>').html('<a href="#" aria-label="Next page"><span class="glyphicon glyphicon-forward" aria-hidden="true"></span></a>');
	if (!this.canGoForward()) {
		nextLink.addClass('disabled');
	} else {
		nextLink.click(function(e) {
			e.stopPropagation();
			grid.nextPage();
			e.preventDefault();
		});
	};
	paginator.append(nextLink);

	var lastLink = $('<li>').html('<a href="#" aria-label="Last page"><span class="glyphicon glyphicon-fast-forward aria-hidden="true"></span></a>');
	if (!this.canGoForward()) {
		lastLink.addClass('disabled');
	} else {
		lastLink.click(function(e) {
			e.stopPropagation();
			grid.lastPage();
			e.preventDefault();
		});
	};
	paginator.append(lastLink);
};


EditableGrid.prototype.tableSorted = function(columnIndex, descending) {
	with (this) {
		// Réinitialise la sélection
		rowSelected(-1, -1);
	}
};
