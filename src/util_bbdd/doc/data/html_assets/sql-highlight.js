(function () {
  // textContent ya es el SQL tal como lo guarda el motor: no se decodifican entidades (S-02, v0.41.1).
  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function highlightSql(source) {
    var html = escapeHtml(source);

    html = html.replace(/(--[^\n]*)/g, '<span class="sql-comment">$1</span>');
    html = html.replace(/('(?:''|[^'])*')/g, '<span class="sql-string">$1</span>');
    html = html.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="sql-number">$1</span>');

    var keywords = [
      "SELECT","FROM","WHERE","GROUP","BY","ORDER","HAVING","LIMIT","OFFSET","JOIN","INNER","LEFT","RIGHT",
      "FULL","OUTER","ON","AS","DISTINCT","UNION","ALL","INSERT","INTO","VALUES","UPDATE","SET","DELETE",
      "CREATE","ALTER","DROP","TABLE","VIEW","INDEX","PRIMARY","KEY","FOREIGN","REFERENCES","CONSTRAINT",
      "UNIQUE","NOT","NULL","DEFAULT","CHECK","AND","OR","IN","EXISTS","LIKE","BETWEEN","CASE","WHEN",
      "THEN","ELSE","END"
    ];
    var types = ["INT","INTEGER","BIGINT","SMALLINT","TINYINT","NUMERIC","DECIMAL","FLOAT","DOUBLE","REAL","CHAR","VARCHAR","TEXT","DATE","DATETIME","TIMESTAMP","BOOLEAN","BLOB","CLOB"];

    var keywordRegex = new RegExp('\\b(' + keywords.join('|') + ')\\b', 'gi');
    var typeRegex = new RegExp('\\b(' + types.join('|') + ')\\b', 'gi');

    html = html.replace(keywordRegex, function (m) { return '<span class="sql-keyword">' + m + '</span>'; });
    html = html.replace(typeRegex, function (m) { return '<span class="sql-type">' + m + '</span>'; });

    return html;
  }

  function run() {
    var blocks = document.querySelectorAll('code.language-sql');
    blocks.forEach(function (block) {
      var raw = block.textContent || "";
      block.innerHTML = highlightSql(raw);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
