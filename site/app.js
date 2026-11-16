(function () {
  var DATA = JSON.parse(document.getElementById('site-data').textContent);
  var contentEl = document.getElementById('content');
  var navEl = document.getElementById('nav');
  var searchInput = document.getElementById('search-input');
  var menuButton = document.getElementById('menu-button');
  var byId = {};
  var haystack = {};

  var KIND_LABELS = {
    skill: 'Skill',
    skillfile: 'Skill file',
    agent: 'Agent',
    command: 'Command',
    hook: 'Hook',
    script: 'Script',
    document: 'Document',
    principle: 'Principle',
    index: 'Index',
    main: 'Main page',
    wiring: 'Wiring'
  };

  var KINDS = {
    skill: { cls: 'skill', mark: '', plural: 'Skills' },
    skillfile: { cls: 'skill', mark: '', plural: 'Skills' },
    agent: { cls: 'agent', mark: '', plural: 'Agents' },
    command: { cls: 'command', mark: '/', plural: 'Commands' },
    hook: { cls: 'hook', mark: '\u21AF', plural: 'Hooks' },
    script: { cls: 'script', mark: '$', plural: 'Scripts' },
    principle: { cls: 'principle', mark: '\u00B6', plural: 'Principles' },
    document: { cls: 'document', mark: '\u00A7', plural: 'Documents' },
    index: { cls: 'document', mark: '\u00A7', plural: 'Documents' }
  };
  var GROUP_ORDER = ['principle', 'skill', 'agent', 'command', 'hook', 'script', 'document', 'page'];
  var firstMain = true;

  DATA.articles.forEach(function (article) {
    byId[article.id] = article;
    haystack[article.id] = (article.title + '\n' + (article.body || article.source || '')).toLowerCase();
  });

  function esc(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function slug(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'section';
  }

  marked.use({
    renderer: {
      html: function (token) {
        var text = typeof token === 'string' ? token : token.text;
        return esc(text);
      },
      image: function (token) {
        return esc(token.text || '');
      }
    }
  });

  function marker(kind) {
    var def = KINDS[kind];
    if (!def) {
      return '';
    }
    return '<span class="k k-' + def.cls + '" aria-hidden="true">' + def.mark + '</span>';
  }

  function kindOf(id) {
    return byId[id] ? byId[id].kind : '';
  }

  function link(id, text) {
    return '<a href="#/' + esc(id) + '">' + esc(text) + '</a>';
  }

  function markedLink(id, text) {
    return '<a class="ml" href="#/' + esc(id) + '">' + marker(kindOf(id)) + '<span>' + esc(text) + '</span></a>';
  }

  function navList(ids) {
    var items = ids.map(function (id) {
      var article = byId[id];
      return '<li data-id="' + esc(id) + '">' + markedLink(id, article ? article.title : id) + '</li>';
    });
    return '<ul>' + items.join('') + '</ul>';
  }

  function renderNav() {
    var html = DATA.nav.map(function (section) {
      var groups = section.groups.map(function (group) {
        var heading = group.title ? '<h4>' + esc(group.title) + '</h4>' : '';
        return heading + navList(group.ids);
      });
      var single = section.groups.length === 1 && section.groups[0].ids.length === 1;
      if (single) {
        var only = section.groups[0].ids[0];
        return '<div class="nav-single"><ul><li data-id="' + esc(only) + '">' +
          markedLink(only, section.title) + '</li></ul></div>';
      }
      return '<details open><summary>' + esc(section.title) + '</summary>' + groups.join('') + '</details>';
    });
    navEl.innerHTML = html.join('');
  }

  function markCurrent(id) {
    var links = navEl.querySelectorAll('a');
    links.forEach(function (anchor) {
      var current = anchor.parentNode.getAttribute('data-id') === id;
      anchor.classList.toggle('current', current);
    });
  }

  function infoItem(entry) {
    return entry.id ? markedLink(entry.id, entry.text) : esc(entry.text);
  }

  function toolItems(row) {
    var first = row.items[0];
    if (row.label !== 'Tools' || row.items.length !== 1 || first.id) {
      return null;
    }
    return first.text.split(/,\s+/).map(function (tool) { return '<code>' + esc(tool) + '</code>'; });
  }

  function infoRow(row) {
    var tools = toolItems(row);
    if (tools) {
      return '<dt>' + esc(row.label) + '</dt><dd><ul class="tools">' +
        tools.map(function (t) { return '<li>' + t + '</li>'; }).join('') + '</ul></dd>';
    }
    var items = row.items.map(infoItem);
    var value = items.length > 1
      ? '<ul>' + items.map(function (i) { return '<li>' + i + '</li>'; }).join('') + '</ul>'
      : items.join('');
    return '<dt>' + esc(row.label) + '</dt><dd>' + value + '</dd>';
  }

  function infobox(article) {
    if (article.kind === 'main' || !article.info.length) {
      return '';
    }
    var rows = article.info.map(infoRow).join('');
    var kind = KIND_LABELS[article.kind] || '';
    return '<div class="infobox"><div class="ib-head">' + marker(article.kind) + '<span>' + esc(kind) +
      '</span></div><dl>' + rows + '</dl></div>';
  }

  function groupOf(kind) {
    return KINDS[kind] ? KINDS[kind].cls : 'page';
  }

  function backlinks(article) {
    var groups = {};
    article.back.filter(function (id) { return byId[id]; }).forEach(function (id) {
      var key = groupOf(byId[id].kind);
      (groups[key] = groups[key] || []).push(id);
    });
    var rows = GROUP_ORDER.filter(function (key) { return groups[key]; }).map(function (key) {
      var first = byId[groups[key][0]].kind;
      var label = KINDS[first] ? KINDS[first].plural : 'Pages';
      var links = groups[key].map(function (id) {
        return '<li>' + markedLink(id, byId[id].title) + '</li>';
      });
      return '<div class="bl-row"><dt>' + marker(first) + '<span>' + label + '</span></dt><dd><ul>' +
        links.join('') + '</ul></dd></div>';
    });
    var body = rows.length ? '<dl class="bl">' + rows.join('') + '</dl>' : '<p class="none">No articles link here.</p>';
    return '<section class="backlinks"><h2 id="what-links-here">What links here</h2>' + body + '</section>';
  }

  function descriptionOf(article) {
    var row = article.info.filter(function (r) { return r.label === 'Description'; })[0];
    return row ? row.items[0].text : '';
  }

  function assignHeadingIds(root) {
    var used = {};
    var heads = root.querySelectorAll('h2, h3');
    heads.forEach(function (head) {
      var base = slug(head.textContent);
      var id = base;
      var n = 2;
      while (used[id]) {
        id = base + '-' + n;
        n += 1;
      }
      used[id] = true;
      head.id = id;
    });
    return heads;
  }

  function contentsBox(heads) {
    if (heads.length < 2) {
      return '';
    }
    var items = [];
    heads.forEach(function (head) {
      var cls = head.tagName === 'H3' ? ' class="sub"' : '';
      items.push('<li' + cls + '><a href="#' + head.id + '">' + esc(head.textContent) + '</a></li>');
    });
    return '<nav class="toc" aria-label="Contents"><div class="toc-title">Contents</div><ol>' +
      items.join('') + '</ol></nav>';
  }

  function wrapTables(root) {
    root.querySelectorAll('table').forEach(function (table) {
      var wrap = document.createElement('div');
      wrap.className = 'table-wrap';
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  function renderBody(article) {
    var holder = document.createElement('div');
    holder.className = 'body';
    holder.innerHTML = marked.parse(article.body || '');
    var heads = assignHeadingIds(holder);
    wrapTables(holder);
    return { html: holder.innerHTML, toc: contentsBox(heads) };
  }

  function renderSource(article) {
    var lead = descriptionOf(article);
    var leadHtml = lead ? '<p class="lead">' + esc(lead) + '</p>' : '';
    return { html: leadHtml + '<pre class="source"><code>' + esc(article.source) + '</code></pre>', toc: '' };
  }

  function header(article) {
    var kind = KIND_LABELS[article.kind] || '';
    var long = article.title.length > 22 ? ' long' : '';
    var path = article.path ? '<code class="path">' + esc(article.path) + '</code>' : '';
    var kindName = KINDS[article.kind] ? '<span class="kindname">' + esc(kind) + '</span>' : '';
    var meta = kindName || path ? '<p class="meta">' + kindName + path + '</p>' : '';
    return '<header class="head"><h1 class="title' + long + '">' + marker(article.kind) +
      '<span class="t">' + esc(article.title) + '</span></h1>' + meta + '</header>';
  }

  function routeStation(id, gate) {
    var kind = kindOf(id);
    var tag = gate ? '<span class="gate-tag">gate</span>' : '';
    return '<a class="stop-link" href="#/' + esc(id) + '"><span class="k st k-' + KINDS[kind].cls +
      '" aria-hidden="true">' + KINDS[kind].mark + '</span>' +
      '<span class="stop-name">' + esc(byId[id].title) + '</span>' + tag + '</a>';
  }

  function routeSpur(route) {
    return '<div class="spur">' + routeStation(route.branch, false) +
      '<span class="spur-note">for larger efforts</span></div>';
  }

  function renderRoute(route, animate) {
    if (!route || !route.stops.length) {
      return '';
    }
    var stops = route.stops.map(function (stop, index) {
      var spur = route.branch && route.branch_from === stop.id ? routeSpur(route) : '';
      return '<li class="stop' + (stop.gate ? ' gate' : '') + (spur ? ' has-spur' : '') +
        '" style="--i:' + index + '">' + routeStation(stop.id, stop.gate) + spur + '</li>';
    });
    var flow = route.coordinator
      ? '<div class="route-flow"><span class="flow-bar"></span><p>' + markedLink(route.coordinator, byId[route.coordinator].title) +
        ' keeps the work moving along the line, from the first stop to the last.</p></div>'
      : '';
    return '<section class="route-map' + (animate ? ' animate' : '') + '" aria-label="How a piece of work moves">' +
      '<div class="route-track"><ol class="route">' + stops.join('') + '</ol><span class="route-line"></span></div>' +
      flow + '</section>';
  }

  function renderArticle(article) {
    var rendered = article.fmt === 'source' ? renderSource(article) : renderBody(article);
    var bodyHtml = article.fmt === 'source' ? rendered.html : '<div class="body">' + rendered.html + '</div>';
    var isMain = article.kind === 'main';
    var hero = isMain ? renderRoute(DATA.route, firstMain) : '';
    var side = infobox(article) + rendered.toc;
    var aside = side ? '<aside class="aside">' + side + '</aside>' : '';
    var cls = 'page' + (isMain ? ' page-main' : '') + (aside ? '' : ' no-aside');
    if (isMain) {
      firstMain = false;
    }
    return '<article class="' + cls + '">' + header(article) + hero + '<div class="cols"><div class="col-main">' +
      bodyHtml + backlinks(article) + '</div>' + aside + '</div></article>';
  }

  function wiringTable(rows) {
    if (!rows.length) {
      return '<p class="none">None.</p>';
    }
    var body = rows.map(function (row) {
      var script = row.id
        ? markedLink(row.id, row.label)
        : esc(row.label) + ' <span class="tag">not included</span>';
      var args = row.args ? ' <code>' + esc(row.args) + '</code>' : '';
      var flags = [];
      if (row.async) { flags.push('async'); }
      if (row.timeout) { flags.push(row.timeout + 's timeout'); }
      return '<tr><th scope="row">' + esc(row.event) + '</th><td>' + (row.matcher ? '<code>' + esc(row.matcher) + '</code>' : '') +
        '</td><td>' + script + args + '</td><td>' + esc(flags.join(', ')) + '</td></tr>';
    });
    return '<div class="table-wrap"><table><thead><tr><th>Event</th><th>Matcher</th><th>Script</th><th>Notes</th></tr></thead><tbody>' +
      body.join('') + '</tbody></table></div>';
  }

  function mcpTable(rows) {
    var body = rows.map(function (row) {
      return '<tr><th scope="row">' + esc(row.name) + '</th><td>' + esc(row.scope) + '</td><td>' +
        esc(row.transport) + '</td><td><code>' + esc(row.url) + '</code></td></tr>';
    });
    return '<div class="table-wrap"><table><thead><tr><th>Server</th><th>Scope</th><th>Transport</th><th>URL or command</th></tr></thead><tbody>' +
      body.join('') + '</tbody></table></div>';
  }

  function renderWiring(article) {
    var wiring = DATA.wiring;
    return '<article class="page page-wide no-aside">' + header(article) +
      '<div class="wiring">' +
      '<p class="intro">Which script runs on which event, read from <code>settings.json</code>, <code>codex/hooks.json</code> and <code>mcp/servers.json</code>.</p>' +
      '<h2 id="claude-code-hooks">Claude Code hooks</h2>' + wiringTable(wiring.claude) +
      '<h2 id="codex-hooks">Codex hooks</h2>' + wiringTable(wiring.codex) +
      '<h2 id="mcp-servers">MCP servers</h2>' + mcpTable(wiring.mcp) +
      '</div></article>';
  }

  function terms(query) {
    return query.toLowerCase().split(/\s+/).filter(Boolean);
  }

  function countIn(text, term) {
    var count = 0;
    var at = text.indexOf(term);
    while (at !== -1) {
      count += 1;
      at = text.indexOf(term, at + term.length);
    }
    return count;
  }

  function snippet(article, words) {
    var text = (article.body || article.source || '').replace(/\s+/g, ' ');
    var lower = text.toLowerCase();
    var at = -1;
    words.forEach(function (word) {
      var found = lower.indexOf(word);
      if (found !== -1 && (at === -1 || found < at)) {
        at = found;
      }
    });
    if (at === -1) {
      return esc(text.slice(0, 140));
    }
    var start = Math.max(0, at - 60);
    var piece = text.slice(start, at + 100);
    var html = esc(piece);
    words.forEach(function (word) {
      var rx = new RegExp(esc(word).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      html = html.replace(rx, function (hit) { return '<mark>' + hit + '</mark>'; });
    });
    return (start > 0 ? '… ' : '') + html + ' …';
  }

  function search(query) {
    var words = terms(query);
    if (!words.length) {
      return [];
    }
    var hits = [];
    DATA.articles.forEach(function (article) {
      var text = haystack[article.id];
      var matched = words.every(function (word) { return text.indexOf(word) !== -1; });
      if (!matched) {
        return;
      }
      var title = article.title.toLowerCase();
      var score = 0;
      words.forEach(function (word) {
        score += (title.indexOf(word) !== -1 ? 50 : 0) + Math.min(countIn(text, word), 40);
      });
      hits.push({ article: article, score: score });
    });
    hits.sort(function (a, b) { return b.score - a.score || a.article.title.localeCompare(b.article.title); });
    return hits;
  }

  function renderSearch(query) {
    var hits = search(query);
    var words = terms(query);
    var items = hits.slice(0, 60).map(function (hit) {
      var article = hit.article;
      return '<li>' + markedLink(article.id, article.title) +
        '<div class="snippet">' + snippet(article, words) + '</div></li>';
    });
    var summary = query
      ? '<p>' + hits.length + ' article' + (hits.length === 1 ? '' : 's') + ' match <b>' + esc(query) + '</b>.</p>'
      : '<p>Type a word in the search box.</p>';
    return '<article class="page no-aside"><header class="head"><h1 class="title"><span class="t">Search results</span></h1></header>' +
      '<div class="cols"><div class="col-main">' + summary + '<ul class="results">' + items.join('') + '</ul></div></div></article>';
  }

  function renderNotFound(id) {
    return '<article class="page no-aside"><header class="head"><h1 class="title"><span class="t">Article not found</span></h1></header>' +
      '<div class="cols"><div class="col-main"><p>There is no article called <code>' + esc(id) +
      '</code>. Try the <a href="#/main">main page</a> or the search box.</p></div></div></article>';
  }

  function parseRoute() {
    var hash = window.location.hash || '';
    var raw = hash.indexOf('#/') === 0 ? hash.slice(2) : '';
    try {
      raw = decodeURIComponent(raw);
    } catch (err) {
      raw = '';
    }
    return raw || 'main';
  }

  function route() {
    var id = parseRoute();
    var html;
    var title = 'Skillbook';

    if (id.indexOf('search/') === 0) {
      var query = id.slice('search/'.length);
      searchInput.value = query;
      html = renderSearch(query);
      title = 'Search: ' + query;
    } else if (byId[id] && byId[id].kind === 'wiring') {
      html = renderWiring(byId[id]);
      title = byId[id].title;
    } else if (byId[id]) {
      html = renderArticle(byId[id]);
      title = byId[id].title;
    } else {
      html = renderNotFound(id);
      title = 'Not found';
    }

    contentEl.innerHTML = html;
    document.title = title === 'Skillbook' ? title : title + ' - Skillbook';
    markCurrent(id);
    setMenu(false);
    window.scrollTo(0, 0);
  }

  function onClick(event) {
    var anchor = event.target.closest ? event.target.closest('a') : null;
    if (!anchor) {
      return;
    }
    var href = anchor.getAttribute('href') || '';
    if (href.charAt(0) !== '#' || href.indexOf('#/') === 0 || href === '#') {
      return;
    }
    event.preventDefault();
    var target = document.getElementById(href.slice(1));
    if (target) {
      target.scrollIntoView();
    }
  }

  document.getElementById('search-form').addEventListener('submit', function (event) {
    event.preventDefault();
    window.location.hash = '#/search/' + encodeURIComponent(searchInput.value.trim());
  });

  function setMenu(open) {
    document.body.classList.toggle('nav-open', open);
    menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuButton.textContent = open ? 'Close' : 'Menu';
  }

  menuButton.addEventListener('click', function () {
    setMenu(!document.body.classList.contains('nav-open'));
  });

  document.addEventListener('click', onClick);
  window.addEventListener('hashchange', route);
  renderNav();
  route();
})();
