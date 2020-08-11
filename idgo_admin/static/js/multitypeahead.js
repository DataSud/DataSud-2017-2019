function MultiTypeahead(id, data, trigger, vertAdjustMenu) {

	trigger = (undefined !== trigger) ? trigger : '';
	var validChars = /^[a-zA-Z]+$/;

	function extractor(query) {
		var result = (new RegExp('([^,; \r\n]+)$')).exec(query);
		if (result && result[1]) {
			return result[1].trim();
		};
		return '';
	};

	var lastUpper = false;
	function strMatcher(id, strs) {
		return function findMatches(q, sync, async) {
			var pos = $(id).caret('pos');
			q = (0 < pos) ? extractor(q.substring(0, pos)) : '';

			if (q.length <= trigger.length) {
				return;
			};

			if (trigger.length) {
				if(trigger != q.substr(0, trigger.length)) {
					return;
				};
				q = q.substr(trigger.length);
			};

			if (!q.match(validChars)) {
				return;
			};

			var firstChar = q.substr(0, 1);
			lastUpper = (firstChar === firstChar.toUpperCase() && firstChar !== firstChar.toLowerCase());

			var cpos = $(id).caret('position');
			$(id).parent().find('.tt-menu').css('left', cpos.left + 'px');
			if (vertAdjustMenu) {
				$(id).parent().find('.tt-menu').css('top', (cpos.top + cpos.height) + 'px');
			};

			var matches = [];
			var matches = [], substrRegex = new RegExp(q, 'i');
			$.each(strs, function(i, str) {
				if (str.length > q.length && substrRegex.test(str)) {
					matches.push(str);
				};
			});

			if (!matches.length) {
				return;
			};

			sync(matches);
		};
	};

	var lastVal = '';
	var lastPos = 0;
	function beforeReplace(event, data) {
		lastVal = $(id).val();
		lastPos = $(id).caret('pos');
		return true;
	};

	function onReplace(event, data) {
		if (!data || !data.length) {
			return;
		};
		if (!lastVal.length) {
			return;
		};

		var root = lastVal.substr(0, lastPos);
		var post = lastVal.substr(lastPos);

		var typed = extractor(root);
		if (!lastUpper && typed.length >= root.length && 0 >= post.length) {
			return;
		}

		var str = root.substr(0, root.length - typed.length);

		str += lastUpper ? (data.substr(0, 1).toUpperCase() + data.substr(1)) : data;
		var cursorPos = str.length;

		str += post;

		$(id).val(str);
		$(id).caret('pos', cursorPos);
	};

	this.typeahead = $(id)
		.typeahead({
			hint: false,
			highlight: false
		}, {
			'limit': 10,
			'source': strMatcher(id, data)
		})
		.on('typeahead:beforeselect', beforeReplace)
		.on('typeahead:beforeautocomplete', beforeReplace)
		.on('typeahead:beforecursorchange', beforeReplace)
		.on('typeahead:selected', function(evt, data) {
			setTimeout(function() {
				onReplace(evt, data);
			}, 0);
		})
		.on('typeahead:autocompleted', onReplace)
		.on('typeahead:cursorchange', onReplace);
};
