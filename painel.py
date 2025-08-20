from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('aniversarios.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    conn = get_db_connection()
    
    aniversarios_mes = conn.execute('''
        SELECT COUNT(*) as total FROM estatisticas 
        WHERE tipo_evento = "aniversario" 
        AND strftime('%Y-%m', data_registro) = strftime('%Y-%m', 'now')
    ''').fetchone()['total']
    
    tempo_empresa_mes = conn.execute('''
        SELECT COUNT(*) as total FROM estatisticas 
        WHERE tipo_evento = "tempo_empresa" 
        AND strftime('%Y-%m', data_registro) = strftime('%Y-%m', 'now')
    ''').fetchone()['total']
    
    hoje = datetime.now()
    proximos_aniversarios = conn.execute('''
        SELECT nome, data_aniversario FROM colaboradores 
        WHERE ativo = 1
    ''').fetchall()
    
    def key_func(colab):
        try:
            data_aniv = datetime.strptime(colab['data_aniversario'], "%d/%m")
            data_aniv = data_aniv.replace(year=hoje.year)
            if data_aniv < hoje:
                data_aniv = data_aniv.replace(year=hoje.year + 1)
            return (data_aniv - hoje).days
        except ValueError:
            return 365
            
    proximos_aniversarios = sorted(proximos_aniversarios, key=key_func)[:10]
    
    conn.close()
    
    return render_template('dashboard.html', 
                         aniversarios=aniversarios_mes,
                         tempo_empresa=tempo_empresa_mes,
                         proximos=proximos_aniversarios)

@app.route('/api/colaboradores')
def api_colaboradores():
    conn = get_db_connection()
    colaboradores = conn.execute('SELECT * FROM colaboradores WHERE ativo = 1').fetchall()
    conn.close()
    
    return jsonify([dict(colab) for colab in colaboradores])

@app.route('/api/estatisticas/<periodo>')
def api_estatisticas(periodo):
    conn = get_db_connection()
    
    if periodo == 'mensal':
        stats = conn.execute('''
            SELECT tipo_evento, COUNT(*) as total 
            FROM estatisticas 
            WHERE strftime('%Y-%m', data_registro) = strftime('%Y-%m', 'now') 
            GROUP BY tipo_evento
        ''').fetchall()
    else:
        stats = conn.execute('''
            SELECT tipo_evento, COUNT(*) as total 
            FROM estatisticas 
            GROUP BY tipo_evento
        ''').fetchall()
    
    conn.close()
    return jsonify([dict(stat) for stat in stats])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('DEBUG', False))