import os
import discord
from discord.ext import commands, tasks
import aiosqlite
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Adicione estas linhas:
import asyncio
from flask import Flask
import threading

app = Flask(__name__)
port = 4000  # Porta que você deseja usar

@app.route('/')
def hello():
    return "Hello World!"

def run_flask():
    app.run(host="0.0.0.0", port=port)

load_dotenv()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

MENSAGENS_TEMPO_EMPRESA = {
    1: "Seu empenho, comprometimento e talento já fazem toda diferença em nossa história. Que seja apenas o começo de uma trajetória de sucesso!",
    2: "Dois anos de dedicação que fortalecem nossa equipe e inspiram todos ao redor. Obrigado por estar conosco nessa jornada!",
    3: "Três anos de contribuição, aprendizado e conquistas. Que venham muitos desafios e vitórias ainda maiores!",
    4: "Quatro anos de resultados e crescimento contínuo. Sua trajetória é um exemplo de profissionalismo e inspiração!",
    5: "Cinco anos construindo história conosco! Que sua dedicação continue transformando nosso time e nossos resultados!",
    6: "Seis anos de comprometimento e sucesso compartilhado. Você é parte essencial do nosso crescimento!",
    7: "Sete anos de conquistas, dedicação e inspiração. Obrigado por fazer parte da nossa história e cultura!"
}

class Database:
    def __init__(self, db_name='aniversarios.db'):
        self.db_name = db_name

    async def init_db(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS colaboradores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER UNIQUE,
                    nome TEXT NOT NULL,
                    setor TEXT,
                    cargo_id INTEGER,
                    data_aniversario TEXT NOT NULL,
                    data_entrada TEXT,
                    imagem_aniversario TEXT,
                    imagem_empresa TEXT,
                    ativo INTEGER DEFAULT 1
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS configuracoes (
                    guild_id INTEGER PRIMARY KEY,
                    canal_aniversarios_id INTEGER,
                    canal_avisos_id INTEGER,
                    hora_notificacao TEXT DEFAULT '09:00',
                    dias_aviso_previo INTEGER DEFAULT 1
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS estatisticas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_evento TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    data_evento TEXT NOT NULL,
                    data_registro TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()

    async def adicionar_colaborador(self, discord_id, nome, setor, cargo_id, data_aniversario, 
                                  data_entrada, imagem_aniversario, imagem_empresa):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT OR REPLACE INTO colaboradores 
                (discord_id, nome, setor, cargo_id, data_aniversario, data_entrada, imagem_aniversario, imagem_empresa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (discord_id, nome, setor, cargo_id, data_aniversario, data_entrada, imagem_aniversario, imagem_empresa))
            await db.commit()

    async def remover_colaborador(self, discord_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('UPDATE colaboradores SET ativo = 0 WHERE discord_id = ?', (discord_id,))
            await db.commit()

    async def obter_colaborador(self, discord_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM colaboradores WHERE discord_id = ? AND ativo = 1', (discord_id,))
            return await cursor.fetchone()

    async def obter_todos_colaboradores(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM colaboradores WHERE ativo = 1')
            return await cursor.fetchall()

    async def obter_aniversariantes_do_dia(self):
        hoje = datetime.now().strftime("%d/%m")
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM colaboradores WHERE data_aniversario = ? AND ativo = 1', (hoje,))
            return await cursor.fetchall()

    async def obter_colaboradores_aniversario_empresa(self):
        hoje = datetime.now()
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM colaboradores WHERE ativo = 1')
            colaboradores = await cursor.fetchall()
            
            result = []
            for colab in colaboradores:
                if colab[6]:  # data_entrada
                    try:
                        data_entrada = datetime.strptime(colab[6], "%d/%m/%Y")
                        if data_entrada.day == hoje.day and data_entrada.month == hoje.month:
                            result.append(colab)
                    except ValueError:
                        continue
            return result

    async def registrar_evento_estatistica(self, tipo_evento, usuario_id, data_evento):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT INTO estatisticas (tipo_evento, usuario_id, data_evento)
                VALUES (?, ?, ?)
            ''', (tipo_evento, usuario_id, data_evento))
            await db.commit()

    async def obter_estatisticas(self, periodo='mensal'):
        async with aiosqlite.connect(self.db_name) as db:
            if periodo == 'mensal':
                cursor = await db.execute('''
                    SELECT tipo_evento, COUNT(*) as total 
                    FROM estatisticas 
                    WHERE strftime('%Y-%m', data_registro) = strftime('%Y-%m', 'now') 
                    GROUP BY tipo_evento
                ''')
            elif periodo == 'anual':
                cursor = await db.execute('''
                    SELECT tipo_evento, COUNT(*) as total 
                    FROM estatisticas 
                    WHERE strftime('%Y', data_registro) = strftime('%Y', 'now') 
                    GROUP BY tipo_evento
                ''')
            else:
                cursor = await db.execute('''
                    SELECT tipo_evento, COUNT(*) as total 
                    FROM estatisticas 
                    GROUP BY tipo_evento
                ''')
            return await cursor.fetchall()

    async def obter_proximos_aniversarios(self, limite=10):
        hoje = datetime.now()
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT nome, data_aniversario FROM colaboradores WHERE ativo = 1')
            colaboradores = await cursor.fetchall()
            
            # Ordenar por proximidade do aniversário
            def key_func(colab):
                try:
                    data_aniv = datetime.strptime(colab[1], "%d/%m")
                    data_aniv = data_aniv.replace(year=hoje.year)
                    if data_aniv < hoje:
                        data_aniv = data_aniv.replace(year=hoje.year + 1)
                    return (data_aniv - hoje).days
                except ValueError:
                    return 365  # Se data inválida, coloca no final
                    
            colaboradores_ordenados = sorted(colaboradores, key=key_func)
            return colaboradores_ordenados[:limite]

    async def obter_configuracoes(self, guild_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM configuracoes WHERE guild_id = ?', (guild_id,))
            return await cursor.fetchone()

    async def salvar_configuracoes(self, guild_id, canal_aniversarios_id, canal_avisos_id, hora_notificacao, dias_aviso_previo):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT OR REPLACE INTO configuracoes 
                (guild_id, canal_aniversarios_id, canal_avisos_id, hora_notificacao, dias_aviso_previo)
                VALUES (?, ?, ?, ?, ?)
            ''', (guild_id, canal_aniversarios_id, canal_avisos_id, hora_notificacao, dias_aviso_previo))
            await db.commit()

db = Database()

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user.name}')
    await db.init_db()
    checar_aniversarios.start()
    enviar_lembretes_administradores.start()
    print('✅ Banco de dados inicializado e tarefas agendadas')

@bot.command(name='registrar')
async def registrar_colaborador(ctx, membro: discord.Member, data_aniversario: str, data_entrada: str = None):
    """Registra um novo colaborador no sistema"""
    try:
        datetime.strptime(data_aniversario, "%d/%m")
        
        if data_entrada:
            datetime.strptime(data_entrada, "%d/%m/%Y")
        
        cargo = next((role for role in membro.roles if role.name != "@everyone"), None)
        
        img_aniversario = f"https://example.com/aniversario/{membro.id}.png"
        img_empresa = f"https://example.com/empresa/{membro.id}.png"
        
        await db.adicionar_colaborador(
            membro.id, 
            membro.display_name, 
            cargo.name if cargo else "Geral", 
            cargo.id if cargo else 0,
            data_aniversario, 
            data_entrada, 
            img_aniversario, 
            img_empresa
        )
        
        await ctx.send(f"✅ {membro.mention} foi registrado com sucesso no sistema de aniversários!")
        
    except ValueError:
        await ctx.send("❌ Formato de data inválido! Use DD/MM para aniversário e DD/MM/AAAA para data de entrada.")

@bot.command(name='configurar')
@commands.has_permissions(administrator=True)
async def configurar_canais(ctx, canal_aniversarios: discord.TextChannel, canal_avisos: discord.TextChannel = None):
    """Configura os canais onde o bot enviará as notificações"""
    try:
        await db.salvar_configuracoes(
            ctx.guild.id, 
            canal_aniversarios.id, 
            canal_avisos.id if canal_avisos else None,
            '09:00',
            1
        )
        
        await ctx.send(f"✅ Configurações salvas! Aniversários serão anunciados em {canal_aniversarios.mention}")
        
    except Exception as e:
        await ctx.send(f"❌ Erro ao configurar: {str(e)}")

async def enviar_mensagem_aniversario(canal, colaborador, tipo="aniversario"):
    try:
        membro = bot.get_user(colaborador[1])
        if not membro:
            return
            
        cargo_mention = f"<@&{colaborador[4]}>" if colaborador[4] else ""
        
        if tipo == "aniversario":
            content = f"🎂 Feliz aniversário {membro.mention}! || @everyone ||"
            titulo = f"Parabéns, {colaborador[2]}! 🎉"
            descricao = f"""Hoje celebramos você, sua dedicação e energia que tornam nosso time mais forte.
Que este novo ciclo seja repleto de conquistas, aprendizado e momentos inesquecíveis!
Cargo/Área: {cargo_mention}"""
            imagem_url = colaborador[7]
            
            await db.registrar_evento_estatistica("aniversario", colaborador[1], datetime.now().strftime("%Y-%m-%d"))
            
        else:
            data_entrada = datetime.strptime(colaborador[6], "%d/%m/%Y")
            anos = datetime.now().year - data_entrada.year
            
            content = f"🏅 Parabéns {membro.mention} pelos {anos} anos de empresa! || @everyone ||"
            titulo = f"{anos} anos de história 🎊"
            descricao = f"{MENSAGENS_TEMPO_EMPRESA.get(anos, 'Parabéns pela trajetória!')}\nCargo/Área: {cargo_mention}"
            imagem_url = colaborador[8]
            
            await db.registrar_evento_estatistica("tempo_empresa", colaborador[1], datetime.now().strftime("%Y-%m-%d"))
        
        embed = discord.Embed(title=titulo, description=descricao, color=0xFFA500)
        if imagem_url:
            embed.set_image(url=imagem_url)
        
        await canal.send(content=content, embed=embed)
        
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")

@tasks.loop(minutes=30)
async def checar_aniversarios():
    agora = datetime.now()
    
    if agora.hour == 9 and agora.minute == 0:
        try:
            for guild in bot.guilds:
                config = await db.obter_configuracoes(guild.id)
                
                if not config:
                    continue
                    
                canal = bot.get_channel(config[1])
                if not canal:
                    continue
                
                aniversariantes = await db.obter_aniversariantes_do_dia()
                for colab in aniversariantes:
                    await enviar_mensagem_aniversario(canal, colab, "aniversario")
                
                aniversario_empresa = await db.obter_colaboradores_aniversario_empresa()
                for colab in aniversario_empresa:
                    await enviar_mensagem_aniversario(canal, colab, "empresa")
                    
        except Exception as e:
            print(f"Erro ao verificar aniversários: {e}")

@bot.command(name='estatisticas')
@commands.has_permissions(administrator=True)
async def mostrar_estatisticas(ctx, periodo: str = 'mensal'):
    try:
        stats = await db.obter_estatisticas(periodo)
        
        if not stats:
            await ctx.send("📊 Nenhuma estatística disponível no momento.")
            return
            
        embed = discord.Embed(
            title=f"📊 Estatísticas de Celebrações ({periodo})",
            color=0x7289DA
        )
        
        total = 0
        for tipo, quantidade in stats:
            embed.add_field(
                name=tipo.capitalize(),
                value=f"{quantidade} evento(s)",
                inline=True
            )
            total += quantidade
            
        embed.set_footer(text=f"Total: {total} celebrações")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Erro ao obter estatísticas: {str(e)}")

@bot.command(name='lembretes')
@commands.has_permissions(administrator=True)
async def configurar_lembretes(ctx, dias_aviso: int = 1, canal: discord.TextChannel = None):
    try:
        config = await db.obter_configuracoes(ctx.guild.id)
        if config:
            canal_id = canal.id if canal else config[2]
            await db.salvar_configuracoes(ctx.guild.id, config[1], canal_id, config[3], dias_aviso)
        else:
            canal_id = canal.id if canal else ctx.channel.id
            await db.salvar_configuracoes(ctx.guild.id, None, canal_id, '09:00', dias_aviso)
        
        await ctx.send(f"✅ Lembretes configurados! Avise com {dias_aviso} dia(s) de antecedência em {canal.mention if canal else 'este canal'}")
        
    except Exception as e:
        await ctx.send(f"❌ Erro ao configurar lembretes: {str(e)}")

@tasks.loop(hours=24)
async def enviar_lembretes_administradores():
    try:
        for guild in bot.guilds:
            config = await db.obter_configuracoes(guild.id)
            
            if not config or not config[2]:
                continue
                
            canal = bot.get_channel(config[2])
            if not canal:
                continue
                
            dias_aviso = config[4] or 1
            
            data_alvo = datetime.now() + timedelta(days=dias_aviso)
            data_str = data_alvo.strftime("%d/%m")
            
            aniversariantes = await db.obter_aniversariantes_do_dia(data_str)
            
            if aniversariantes:
                mensagem = f"📋 **Lembrete de Aniversários** - {data_alvo.strftime('%d/%m/%Y')}\n\n"
                mensagem += "**Próximos aniversariantes:**\n"
                
                for colab in aniversariantes:
                    mensagem += f"• {colab[2]} ({colab[5]})\n"
                    
                mensagem += f"\n*Lembrete com {dias_aviso} dia(s) de antecedência*"
                
                await canal.send(mensagem)
                
    except Exception as e:
        print(f"Erro ao enviar lembretes: {e}")

@bot.command(name='testar_aniversario')
@commands.has_permissions(administrator=True)
async def testar_aniversario(ctx, membro: discord.Member):
    try:
        colab = await db.obter_colaborador(membro.id)
        if colab:
            await enviar_mensagem_aniversario(ctx.channel, colab, "aniversario")
        else:
            await ctx.send("❌ Membro não encontrado no banco de dados.")
    except Exception as e:
        await ctx.send(f"❌ Erro no teste: {str(e)}")

@bot.command(name='listar')
async def listar_colaboradores(ctx):
    try:
        colaboradores = await db.obter_todos_colaboradores()
        
        if not colaboradores:
            await ctx.send("📝 Nenhum colaborador registrado ainda.")
            return
        
        embed = discord.Embed(title="👥 Colaboradores Registrados", color=0x00ff00)
        
        for colab in colaboradores:
            user = bot.get_user(colab[1])
            mention = user.mention if user else f"ID: {colab[1]}"
            embed.add_field(
                name=colab[2],
                value=f"{mention} | Aniversário: {colab[5]} | Entrada: {colab[6] or 'N/A'}",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Erro ao listar colaboradores: {str(e)}")

# async def keep_alive():
#     async def handle(request):
#         return web.Response(text="Bot está rodando!")
#     app = web.Application()
#     app.router.add_get("/", handle)
#     runner = web.AppRunner(app)
#     await runner.setup()
#     site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
#     await site.start()

if __name__ == "__main__":
    token = os.environ.get('DISCORD_TOKEN')

    # Inicie o Flask em uma thread separada
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    if token:
        bot.run(token)
    else:
        print("❌ Token não encontrado. Configure a variável de ambiente DISCORD_TOKEN.")
