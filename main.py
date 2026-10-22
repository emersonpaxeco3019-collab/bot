import os
import re
import asyncio
import json
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()
from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
  return "Bot Politica Brasil Online!"

def run():
  app.run(host='0.0.0.0', port=10000)

t = Thread(target=run)
t.start()
    t = Thread(target=run)
    t.start()


import discord
from discord.ext import commands

intents = discord.Intents.all()
intents.message_content = True  # ✅ Habilitar leitura de conteúdo das mensagens

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.before_invoke
async def defer_slash_command(ctx):
    if ctx.interaction is not None and not ctx.interaction.response.is_done():
        await ctx.defer()


DATA_FILE = os.path.join(os.path.dirname(__file__), "sales.json")


class Sales(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sales = self._load_sales()

    def _load_sales(self):
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"❌ Não foi possível carregar vendas: {e}")
            return []

    def _save_sales(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.sales, f, ensure_ascii=False, indent=2)

    @commands.hybrid_command(name="venda", aliases=["vender"])
    async def venda(self, ctx, produto: str, quantidade: int, valor: float):
        """Registra uma venda. Ex: !venda camisa 2 49.90"""
        total = round(quantidade * valor, 2)
        registro = {
            "produto": produto,
            "quantidade": quantidade,
            "valor_unitario": round(valor, 2),
            "total": total,
            "autor": str(ctx.author),
            "canal": ctx.channel.name,
        }
        self.sales.append(registro)
        self._save_sales()
        await ctx.send(f"✅ Venda registrada: {produto} x{quantidade} por R$ {total:.2f}")

    @commands.hybrid_command(name="vendas", aliases=["sales"])
    async def vendas(self, ctx):
        """Mostra o resumo das vendas registradas."""
        if not self.sales:
            await ctx.send("📭 Nenhuma venda registrada ainda.")
            return

        total_vendas = len(self.sales)
        total_arrecadado = round(sum(item["total"] for item in self.sales), 2)
        por_produto = {}
        for item in self.sales:
            por_produto[item["produto"]] = por_produto.get(item["produto"], 0) + item["total"]

        resumo = "\n".join(
            f"- {produto}: R$ {valor:.2f}" for produto, valor in por_produto.items()
        )
        await ctx.send(
            f"💰 Resumo de vendas\n"
            f"Vendas registradas: {total_vendas}\n"
            f"Total arrecadado: R$ {total_arrecadado:.2f}\n"
            f"Por produto:\n{resumo}"
        )


class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _sanitize_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
        return cleaned or "ticket"

    async def _get_or_create_category(self, guild):
        for category in guild.categories:
            if category.name.lower() == "tickets":
                return category
        return await guild.create_category("Tickets")

    async def _get_or_create_support_role(self, guild):
        role_name = os.getenv("TICKET_SUPPORT_ROLE_NAME", "Atendimento")
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            return role
        return await guild.create_role(name=role_name, reason="Cargo de atendimento para tickets")

    async def _get_or_create_log_channel(self, guild):
        channel_name = os.getenv("TICKET_LOG_CHANNEL_NAME", "ticket-logs")
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            return channel
        category = await self._get_or_create_category(guild)
        return await guild.create_text_channel(channel_name, category=category, topic="Logs de tickets")

    async def _send_log(self, guild, message: str):
        try:
            channel = await self._get_or_create_log_channel(guild)
            await channel.send(message)
        except Exception as e:
            print(f"❌ Não foi possível registrar log de ticket: {e}")

    @commands.hybrid_command(name="ticket", aliases=["abrirticket"])
    async def ticket(self, ctx, *, motivo: str = "Sem motivo"):
        """Abre um ticket para atendimento no servidor. Ex: !ticket preciso de ajuda"""
        if ctx.guild is None:
            await ctx.send("Use este comando em um servidor.")
            return

        existing = discord.utils.get(
            ctx.guild.text_channels,
            topic=f"ticket|{ctx.author.id}"
        )
        if existing:
            await ctx.send(f"Você já possui um ticket aberto: {existing.mention}")
            return

        category = await self._get_or_create_category(ctx.guild)
        support_role = await self._get_or_create_support_role(ctx.guild)
        base_name = self._sanitize_name(f"{ctx.author.name}-{ctx.author.discriminator}")
        channel_name = f"ticket-{base_name}"
        suffix = 1
        while discord.utils.get(ctx.guild.text_channels, name=channel_name):
            channel_name = f"ticket-{base_name}-{suffix}"
            suffix += 1

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        }

        for role in ctx.guild.roles:
            if role.permissions.administrator or role.permissions.manage_channels or role.permissions.manage_messages:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)

        channel = await ctx.guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"ticket|{ctx.author.id}"
        )
        await channel.send(
            f"Olá {ctx.author.mention}! Seu ticket foi aberto.\n"
            f"Motivo: {motivo}\n\n"
            f"A equipe de atendimento {support_role.mention} irá te ajudar em breve.\n"
            f"Use `!fecharticket` para fechar este atendimento quando terminar."
        )
        await ctx.send(f"✅ Ticket criado: {channel.mention}")

    @commands.hybrid_command(name="fecharticket", aliases=["close"])
    async def fechar_ticket(self, ctx):
        """Fecha o ticket atual."""
        if ctx.channel.name.startswith("ticket-"):
            topic = ctx.channel.topic or ""
            if topic.startswith("ticket|"):
                owner_id = int(topic.split("|", 1)[1])
                if ctx.author.id != owner_id and not ctx.author.guild_permissions.manage_channels:
                    await ctx.send("Você não pode fechar este ticket.")
                    return

                await ctx.send("🗑️ Fechando ticket...")
                requester = ctx.guild.get_member(owner_id) or ctx.author
                await self._send_log(
                    ctx.guild,
                    f"🎫 Ticket fechado\n"
                    f"Usuário: {requester.mention if hasattr(requester, 'mention') else requester}\n"
                    f"Canal: {ctx.channel.name}\n"
                    f"Fechado por: {ctx.author.mention}"
                )
                await ctx.channel.delete()
                return

        await ctx.send("Este comando só pode ser usado dentro de um ticket.")


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warns = {}

    async def _get_or_create_mute_role(self, guild):
        role = discord.utils.get(guild.roles, name="Silenciado")
        if role:
            return role

        role = await guild.create_role(name="Silenciado", reason="Role para silenciar membros")
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel)):
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False, connect=False, read_message_history=False, send_messages_in_threads=False)
        return role

    @commands.hybrid_command(name="limpar")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def limpar(self, ctx, quantidade: int = 5):
        """Apaga mensagens. Ex: !limpar 50"""
        if quantidade <= 0:
            await ctx.send("❌ Quantidade deve ser maior que 0!")
            return

        if quantidade > 100:
            await ctx.send("❌ Máximo de 100 mensagens por vez!")
            return

        try:
            deleted = await ctx.channel.purge(limit=quantidade + 1)
            count = max(0, len(deleted) - 1)

            msg = await ctx.send(f'🧹 Apaguei {count} mensagens!')
            await asyncio.sleep(2)
            await msg.delete()

        except discord.Forbidden:
            await ctx.send('❌ Não tenho permissão para apagar mensagens neste canal.')
        except discord.HTTPException as e:
            await ctx.send(f'❌ Erro ao apagar mensagens: {e}')
        except Exception as e:
            print(f"❌ Erro no comando limpar: {e}")
            await ctx.send(f'❌ Erro: {e}')

    @commands.hybrid_command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, membro: discord.Member, *, motivo="Sem motivo"):
        """Bane um membro. Ex: !ban @usuario spam"""
        if membro.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ Você não pode banir esse membro.")
            return
        await membro.ban(reason=motivo)
        await ctx.send(f'🔒 {membro} foi banido. Motivo: {motivo}')

    @commands.hybrid_command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, motivo="Sem motivo"):
        """Desbane um usuário. Ex: !unban 123456789012345678"""
        await ctx.guild.unban(user, reason=motivo)
        await ctx.send(f'✅ {user} foi liberado do ban. Motivo: {motivo}')

    @commands.hybrid_command(name="mute")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, membro: discord.Member, *, motivo="Sem motivo"):
        """Silencia um membro. Ex: !mute @usuario spam"""
        role = await self._get_or_create_mute_role(ctx.guild)
        if role in membro.roles:
            await ctx.send(f"⚠️ {membro} já está silenciado.")
            return
        await membro.add_roles(role, reason=motivo)
        await ctx.send(f'🔇 {membro} foi silenciado. Motivo: {motivo}')

    @commands.hybrid_command(name="desmutar", aliases=["unmute"])
    @commands.has_permissions(manage_roles=True)
    async def desmutar(self, ctx, membro: discord.Member):
        """Remove o silenciamento de um membro."""
        role = discord.utils.get(ctx.guild.roles, name="Silenciado")
        if not role or role not in membro.roles:
            await ctx.send(f"⚠️ {membro} não está silenciado.")
            return
        await membro.remove_roles(role)
        await ctx.send(f'🔊 {membro} foi desmutado.')

    @commands.hybrid_command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, membro: discord.Member, *, motivo="Sem motivo"):
        """Adiciona aviso para um membro."""
        self.warns.setdefault(str(membro.id), [])
        self.warns[str(membro.id)].append({"motivo": motivo, "moderador": str(ctx.author)})
        await ctx.send(f'⚠️ {membro} recebeu um aviso. Total: {len(self.warns[str(membro.id)])}')

    @commands.hybrid_command(name="warns")
    @commands.has_permissions(manage_messages=True)
    async def warns(self, ctx, membro: discord.Member = None):
        """Mostra avisos de um membro."""
        if membro is None:
            await ctx.send("⚠️ Use: !warns @usuario")
            return
        avisos = self.warns.get(str(membro.id), [])
        if not avisos:
            await ctx.send(f"✅ {membro} não possui avisos.")
            return
        text = "\n".join(f"{i + 1}. {a['motivo']} (por {a['moderador']})" for i, a in enumerate(avisos))
        await ctx.send(f"⚠️ Avisos de {membro}:\n{text}")

    @commands.hybrid_command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, membro: discord.Member, *, motivo="Sem motivo"):
        """Expulsa alguém. Ex: !kick @user spam"""
        if membro.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ Você não pode expulsar esse membro.")
            return
        await membro.kick(reason=motivo)
        await ctx.send(f'👢 {membro} foi expulso. Motivo: {motivo}')

    @commands.hybrid_command(name="perms")
    async def perms(self, ctx):
        """Exibe permissões do bot e do usuário neste canal."""
        channel = ctx.channel
        bot_member = ctx.guild.me
        bot_perms = channel.permissions_for(bot_member)
        user_perms = channel.permissions_for(ctx.author)

        def fmt(perms):
            keys = [
                'manage_messages', 'manage_channels', 'send_messages', 'view_channel',
                'embed_links', 'read_message_history', 'add_reactions', 'manage_roles'
            ]
            return '\n'.join(f"{k}: {getattr(perms, k)}" for k in keys)

        await ctx.send(f"**Permissões do bot:**\n{fmt(bot_perms)}\n\n**Permissões do usuário:**\n{fmt(user_perms)}")


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data = {}

    def _get_or_create_user(self, user_id):
        return self.user_data.setdefault(str(user_id), {"money": 0, "daily": 0, "rank": 1})

    @commands.hybrid_command(name="rolar")
    async def rolar(self, ctx, lados: int = 6):
        """Rola um dado. Ex: !rolar 20"""
        if lados <= 0:
            await ctx.send("❌ O dado precisa ter um número positivo de lados.")
            return
        import random
        valor = random.randint(1, lados)
        await ctx.send(f'🎲 Você rolou um dado de {lados} e saiu: {valor}')

    @commands.hybrid_command(name="roll", aliases=["r"])
    async def roll(self, ctx, lados: int = 6):
        """Alias para rolar dados."""
        await self.rolar(ctx, lados)

    @commands.hybrid_command(name="coinflip", aliases=["moeda", "caraoucoroa"])
    async def coinflip(self, ctx):
        """Cara ou coroa."""
        import random
        resultado = random.choice(["Cara", "Coroa"])
        await ctx.send(f'🪙 Resultado: {resultado}')

    @commands.hybrid_command(name="dado")
    async def dado(self, ctx, lados: int = 6):
        """Alias para rolar dados."""
        await self.rolar(ctx, lados)

    @commands.hybrid_command(name="escolha", aliases=["choice"])
    async def escolha(self, ctx, *, opcoes: str):
        """Escolhe uma opção aleatória. Ex: !escolha pedra papel tesoura"""
        opcoes = opcoes.replace(",", " ").split()
        if not opcoes:
            await ctx.send("❌ Informe pelo menos uma opção para eu escolher.")
            return
        import random
        await ctx.send(f'🎯 Minha escolha: {random.choice(opcoes)}')

    @commands.hybrid_command(name="abracar")
    async def abracar(self, ctx, membro: discord.Member = None):
        """Abraça alguém."""
        if membro is None or membro == ctx.author:
            await ctx.send(f"{ctx.author.mention} deu um abraço forte em si mesmo! 🤗")
            return
        await ctx.send(f"{ctx.author.mention} abraçou {membro.mention}! 🤗")

    @commands.hybrid_command(name="beijar")
    async def beijar(self, ctx, membro: discord.Member = None):
        """Beija alguém."""
        if membro is None or membro == ctx.author:
            await ctx.send(f"{ctx.author.mention} deu um beijinho no espelho 😘")
            return
        await ctx.send(f"{ctx.author.mention} beijou {membro.mention}! 😘")

    @commands.hybrid_command(name="socar")
    async def socar(self, ctx, membro: discord.Member = None):
        """Soca alguém."""
        if membro is None or membro == ctx.author:
            await ctx.send(f"{ctx.author.mention} deu um soco no ar! 😬")
            return
        await ctx.send(f"{ctx.author.mention} socou {membro.mention}! 😵")

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx):
        """Mostra a latência do bot."""
        await ctx.send(f'🏓 Pong! Latência: {round(self.bot.latency * 1000)}ms')

    @commands.hybrid_command(name="carteira")
    async def carteira(self, ctx):
        """Mostra a carteira do usuário."""
        user = self._get_or_create_user(ctx.author.id)
        await ctx.send(f"💰 {ctx.author.mention} tem R$ {user['money']} na carteira.")

    @commands.hybrid_command(name="daily")
    async def daily(self, ctx):
        """Recompensa diária."""
        import time
        user = self._get_or_create_user(ctx.author.id)
        now = int(time.time())
        if now - user['daily'] < 86400:
            await ctx.send("⏳ Você já coletou o daily hoje. Tente mais tarde.")
            return
        user['money'] += 100
        user['daily'] = now
        await ctx.send(f"💸 {ctx.author.mention} coletou o daily e ganhou R$ 100!")

    @commands.hybrid_command(name="rank")
    async def rank(self, ctx):
        """Mostra o rank do usuário."""
        user = self._get_or_create_user(ctx.author.id)
        await ctx.send(f"🏆 {ctx.author.mention} está no rank {user['rank']} e tem R$ {user['money']}.")

    @commands.hybrid_command(name="adivinha")
    async def adivinha(self, ctx, numero: int = None):
        """Jogo de adivinhação. Ex: !adivinha 7"""
        import random
        alvo = random.randint(1, 10)
        if numero is None:
            await ctx.send(f"🎯 Tente adivinhar! Escolha um número de 1 a 10. Ex: !adivinha 7")
            return
        if 1 <= numero <= 10:
            if numero == alvo:
                await ctx.send(f"✅ Acertou! O número era {alvo}.")
            else:
                await ctx.send(f"❌ Errou! O número era {alvo}. Tente novamente!")
        else:
            await ctx.send("❌ Escolha um número entre 1 e 10.")

    @commands.hybrid_command(name="jokenpo", aliases=["ppt", "pedra"])
    async def jokenpo(self, ctx, escolha: str = None):
        """Jogo de pedra, papel e tesoura. Ex: !jokenpo pedra"""
        import random
        opcoes = ["pedra", "papel", "tesoura"]
        bot_escolha = random.choice(opcoes)
        if escolha is None:
            await ctx.send(f"✊ 📄 ✂️ Escolha uma opção: pedra, papel ou tesoura. Ex: !jokenpo papel")
            return
        escolha = escolha.lower()
        if escolha not in opcoes:
            await ctx.send("❌ Opção inválida. Use: pedra, papel ou tesoura.")
            return
        if escolha == bot_escolha:
            await ctx.send(f"🤝 Empate! Eu também escolhi {bot_escolha}.")
        elif (
            (escolha == "pedra" and bot_escolha == "tesoura") or
            (escolha == "papel" and bot_escolha == "pedra") or
            (escolha == "tesoura" and bot_escolha == "papel")
        ):
            await ctx.send(f"🎉 Você venceu! Eu escolhi {bot_escolha}.")
        else:
            await ctx.send(f"😅 Eu venci! Escolhi {bot_escolha}.")

    @commands.hybrid_command(name="quiz")
    async def quiz(self, ctx):
        """Quiz rápido de múltipla escolha."""
        import random
        perguntas = [
            ("Qual é o maior planeta do Sistema Solar?", ["Terra", "Júpiter", "Marte", "Vênus"], 2),
            ("Qual é a capital do Brasil?", ["Rio de Janeiro", "Brasília", "São Paulo", "Salvador"], 2),
            ("Qual é o maior oceano do mundo?", ["Atlântico", "Índico", "Pacífico", "Ártico"], 3),
        ]
        pergunta, opcoes, correta = random.choice(perguntas)
        await ctx.send(f"❓ {pergunta}\n1. {opcoes[0]}\n2. {opcoes[1]}\n3. {opcoes[2]}\n4. {opcoes[3]}\nResponda com o número da alternativa.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            resposta = await self.bot.wait_for('message', check=check, timeout=20)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Tempo esgotado! Tente novamente.")
            return

        escolha = int(resposta.content)
        if escolha == correta + 1:
            await ctx.send("✅ Correto! Você mandou bem.")
        else:
            await ctx.send(f"❌ Resposta errada. A correta era {opcoes[correta]}.")


class ServerTools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="servidor")
    async def servidor(self, ctx):
        """Informações do servidor."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("Use este comando em um servidor.")
            return
        await ctx.send(
            f"📊 Informações do servidor\n"
            f"Nome: {guild.name}\n"
            f"Membros: {guild.member_count}\n"
            f"Dono: {guild.owner}\n"
            f"Canais: {len(guild.channels)}"
        )

    @commands.hybrid_command(name="serverinfo", aliases=["server", "info"])
    async def serverinfo(self, ctx):
        """Mostra dados do servidor."""
        guild = ctx.guild
        if guild is None:
            await ctx.send("Use este comando em um servidor.")
            return
        await ctx.send(
            f"🛠️ Nome: {guild.name}\n"
            f"👥 Membros: {guild.member_count}\n"
            f"🧑‍💼 Dono: {guild.owner}\n"
            f"📅 Criado em: {guild.created_at.strftime('%d/%m/%Y')}"
        )

    @commands.hybrid_command(name="avatar")
    async def avatar(self, ctx, membro: discord.Member = None):
        """Mostra o avatar de um usuário."""
        user = membro or ctx.author
        await ctx.send(user.display_avatar.url)

    @commands.hybrid_command(name="say")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, mensagem: str):
        """Repete uma mensagem."""
        await ctx.message.delete()
        await ctx.send(mensagem)

    @commands.hybrid_command(name="anuncio")
    @commands.has_permissions(manage_messages=True)
    async def anuncio(self, ctx, *, texto: str):
        """Envia uma mensagem de anúncio importante."""
        await ctx.send(f"📣 Anúncio: {texto}")

    @commands.hybrid_command(name="status")
    async def status(self, ctx):
        """Mostra o status do bot."""
        await ctx.send("✅ Bot online e funcionando!")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f"📨 Mensagem recebida de {message.author}: {message.content}")
    await bot.process_commands(message)


@bot.event
async def on_error(event, *args, **kwargs):
    """Captura erros silenciosos"""
    print(f"❌ Erro no evento '{event}':")
    import traceback
    traceback.print_exc()


@bot.event
async def on_message(message):
    """Debug: Print all messages received."""
    if message.author == bot.user:
        return
    print(f"📨 Mensagem recebida de {message.author}: {message.content}")
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    """Trata erros de comandos."""
    if isinstance(error, commands.CommandNotFound):
        print(f"⚠️ Comando não encontrado: {ctx.message.content}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Faltam argumentos! Use: !help {ctx.command.name}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
    else:
        print(f"❌ Erro no comando {ctx.command}: {error}")
        await ctx.send(f"❌ Erro ao executar comando: {error}")


@bot.tree.error
async def on_app_command_error(interaction, error):
    import traceback

    print(f"❌ Erro no comando slash: {error!r}")
    traceback.print_exception(error)

    message = "❌ O comando falhou. A causa detalhada foi registrada no terminal."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    print(f'📦 Cogs carregados: {list(bot.cogs.keys())}')
    print(f'📝 Comandos prefix: {[cmd.name for cmd in bot.commands]}')
    print(f'👁️ Servidores que o bot está: {len(bot.guilds)}')
    for guild in bot.guilds:
        print(f'   - {guild.name} (ID: {guild.id})')

    if not getattr(bot, "slash_commands_synced", False):
        try:
            synced = await bot.tree.sync()
            bot.slash_commands_synced = True
            print(f"✅ Comandos slash sincronizados: {len(synced)}")
        except Exception as e:
            print(f"❌ Não foi possível sincronizar comandos slash: {e}")
    
    # Set presence online with activity and start keepalive task
    activity = discord.Game("Online")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    
    if not hasattr(bot, 'keepalive_task'):
        bot.keepalive_task = asyncio.create_task(keep_alive())

async def verify_discord_request(request, body):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    public_key = os.getenv("DISCORD_PUBLIC_KEY")

    if not public_key:
        raise web.HTTPInternalServerError(text="DISCORD_PUBLIC_KEY not configured")

    if not signature or not timestamp:
        raise web.HTTPUnauthorized(text="Missing signature headers")

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
    except (BadSignatureError, Exception):
        raise web.HTTPUnauthorized(text="Invalid request signature")

async def handle_interacao(request):
    body = await request.read()
    await verify_discord_request(request, body)

    try:
        data = json.loads(body.decode())
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    if data.get("type") == 1:
        return web.json_response({"type": 1})

    if data.get("type") == 2:
        return web.json_response({"type": 4, "data": {"content": "Interação recebida!"}})

    channel_id = data.get("channel_id")
    message = data.get("message")

    if not channel_id or not message:
        return web.json_response({"error": "channel_id and message are required"}, status=400)

    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return web.json_response({"error": "Channel not found"}, status=404)

    await channel.send(message)
    return web.json_response({"status": "ok", "sent_to": channel_id})

async def start_web_server():
    try:
        app = web.Application()
        app.router.add_post("/interacao", handle_interacao)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
    except Exception as e:
        print(f"⚠️ Aviso ao iniciar servidor web: {e}")


async def keep_alive():
    """Periodically ensure the bot presence remains online to avoid showing offline."""
    while True:
        try:
            activity = discord.Game("Online")
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except Exception as e:
            print("Keepalive error:", e)
        await asyncio.sleep(300)

async def main():
    # Adicionar cogs ANTES de conectar
    await bot.add_cog(Mod(bot))
    await bot.add_cog(Sales(bot))
    await bot.add_cog(TicketSystem(bot))
    await bot.add_cog(Fun(bot))
    await bot.add_cog(ServerTools(bot))
    print(f"✅ Cogs adicionados: {list(bot.cogs.keys())}")
    
    # Iniciar servidor web
    keep_alive()
    print("✅ HTTP endpoint disponível em http://0.0.0.0:8080/interacao")
    
    
    
   
    
    # Conectar ao Discord
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ ERRO: DISCORD_TOKEN não encontrado no arquivo .env")
        return
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ Erro fatal ao conectar: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✋ Bot parado pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
bot.run(os.getenv("DISCORD_TOKEN"))
