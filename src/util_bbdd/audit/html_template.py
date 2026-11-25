"""Plantilla HTML del informe de auditoría (movida desde ``util_bbdd.bulk._audit.html_template``, sesión 2026-10-02c).

Los textos fijos son marcadores (``$l_*``) que ``AuditExporters`` rellena, ya escapados, con el catálogo ``audit`` del
idioma de salida (5.10.0).
"""

from string import Template

AUDIT_HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="$lang">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>$l_title</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; border-left: 4px solid #007bff; padding-left: 10px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-box { background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }
        .stat-label { font-size: 12px; color: #666; text-transform: uppercase; }
        .stat-value { font-size: 24px; font-weight: bold; color: #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background-color: #007bff; color: white; padding: 12px; text-align: left; }
        td { padding: 10px; border-bottom: 1px solid #ddd; }
        tr:hover { background-color: #f0f0f0; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>&#128202; $l_heading</h1>
        <p>$l_generated</p>

        <h2>$l_general_stats</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-label">$l_stat_operations</div>
                <div class="stat-value">$total_operaciones</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">$l_stat_rows</div>
                <div class="stat-value">$total_filas</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">$l_stat_total_time</div>
                <div class="stat-value">$tiempo_total</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">$l_stat_avg_time</div>
                <div class="stat-value">$tiempo_promedio</div>
            </div>
        </div>

        <h2>$l_last_operations</h2>
        $tabla_ultimas_ops

        <h2>$l_by_type</h2>
        $tabla_por_tipo

        <h2>$l_by_table</h2>
        $tabla_por_tabla

        <div class="footer">
            <p>$l_footer</p>
        </div>
    </div>
</body>
</html>""")

__all__: list[str] = ["AUDIT_HTML_TEMPLATE"]
