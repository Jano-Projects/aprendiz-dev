"""
Servidor HTTP local (FastAPI).

Ele só escuta em 127.0.0.1 — ou seja, apenas o próprio computador acessa.
Nada sai para a internet. O botão "Loja oficial" não muda isso: ele só pede
ao navegador do sistema que abra o endereço da loja (fixo no código).

A interface (pasta web/) conversa com estas rotas via fetch() em JSON:

    GET    /                              → a interface de chat
    GET    /api/status                    → versão e contagens
    GET    /api/algoritmos                → opções do seletor
    POST   /api/chat                      → envia mensagem, recebe resposta + explicação
    POST   /api/chat/fluxo                → o mesmo, AO VIVO: uma linha JSON por etapa (2.4)
    GET    /api/modelo                    → ficha técnica: componentes e parâmetros (2.4)
    POST   /api/corrigir                  → corrige uma resposta (vira ensinamento)
    GET    /api/normas                    → normas da língua dos addons ativos (0.8+)
    POST   /api/revisar                   → revisa um texto pela norma escolhida (0.8+)
    POST   /api/sinal                     → "sinal de vida" da interface (ver desktop.py)
    POST   /api/resetar                   → volta ao estado inicial (com backup antes)
    POST   /api/addons/pacote/inspecionar → o que vem num .aprendiz-pacote (sem instalar)
    POST   /api/addons/pacote             → instala todos os addons do pacote, na ordem
    POST   /api/loja-oficial              → abre a loja oficial de addons no navegador
                                            (opcional: {"addon": id} já filtra a loja)

    GET    /api/conversas                 → lista conversas
    GET    /api/conversas/{id}/mensagens  → histórico de uma conversa
    PATCH  /api/conversas/{id}            → renomeia
    DELETE /api/conversas/{id}            → apaga

    GET    /api/conhecimentos?filtro=     → lista a base
    POST   /api/conhecimentos             → ensina (formulário)
    PUT    /api/conhecimentos/{id}        → edita
    DELETE /api/conhecimentos/{id}        → remove
    POST   /api/importar                  → importa um arquivo .txt/.md

    GET    /api/addons                    → addons instalados
    POST   /api/addons/inspecionar        → lê um .aprendiz SEM instalar (confirmação)
    POST   /api/addons                    → instala/atualiza um arquivo .aprendiz
    GET    /api/addons/grupos             → addons agrupados pelo padrão recomendado
    POST   /api/addons/grupo              → ativa/desativa vários addons de uma vez
    PUT    /api/padrao                    → algoritmos padrão de busca e resposta
    PATCH  /api/addons/{id}               → ativa ou desativa
    DELETE /api/addons/{id}               → remove

    GET    /api/exportar                  → o que pode virar addon (prévia, com avisos)
    POST   /api/exportar/recomendar       → testa os algoritmos com os itens marcados
    POST   /api/exportar                  → gera o .aprendiz com os itens marcados

    GET    /api/configuracoes             → parâmetros e personalização em vigor
    PUT    /api/configuracoes/{chave}     → o dono define um valor
    DELETE /api/configuracoes/{chave}     → volta ao valor do addon ou ao padrão

    GET    /api/linguagem                 → banco de linguagem
    POST   /api/linguagem/{tabela}        → adiciona abreviação/sinônimo/exemplo
    DELETE /api/linguagem/{tabela}/{chave}

A documentação interativa gerada pelo FastAPI fica em /docs — ótima para
estudar e testar as rotas sem a interface.
"""

from __future__ import annotations

import base64
import binascii
import json
import queue
import re
import threading
import time
from urllib.parse import quote
import webbrowser
from typing import Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aprendiz import config
from aprendiz.addons import ErroAddon
from aprendiz.algoritmos import listar_algoritmos
from aprendiz.core import Assistente, exportacao, monitor
from aprendiz.linguagem import normalizar
from aprendiz.memoria import Banco


# ---------------------------------------------------------------- modelos (JSON)
class PedidoChat(BaseModel):
    mensagem: str = Field(min_length=1, max_length=5000)
    conversa_id: str | None = None
    busca: str | None = None     # sem valor → o padrão das Configurações
    resposta: str | None = None


class PedidoRevisao(BaseModel):
    texto: str = Field(..., min_length=1, max_length=20_000)
    norma: str | None = Field(None, max_length=10)


class PedidoCorrecao(BaseModel):
    mensagem_id: str
    resposta_correta: str = Field(min_length=1)


class PedidoConhecimento(BaseModel):
    conteudo: str = Field(min_length=1)
    pergunta: str | None = None


class PedidoImportacao(BaseModel):
    nome: str
    texto: str = Field(min_length=1)


class PedidoReset(BaseModel):
    conhecimentos: bool = True
    linguagem: bool = True
    conversas: bool = True
    addons: bool = True
    configuracoes: bool = True
    confirmacao: str  # precisa ser exatamente "RESETAR"


class PedidoAddon(BaseModel):
    # O arquivo vai em base64 dentro do JSON: assim não precisamos de
    # dependência extra para upload "multipart".
    nome_arquivo: str
    conteudo_base64: str
    # Opções da tela de confirmação (só valem ao instalar):
    usar_recomendacao: bool = False   # vira o padrão de busca/resposta do dono
    ativar_grupo: bool = False        # ativa os addons do mesmo grupo


class PedidoConfiguracao(BaseModel):
    valor: Any


class PedidoExportacao(BaseModel):
    manifesto: dict[str, Any]
    conhecimentos: list[str] = []
    abreviacoes: list[str] = []
    sinonimos: list[str] = []
    parametros: list[str] = []
    personalizacao: list[str] = []
    dependencias: list[str] = []
    recomendado: dict[str, str] | None = None


class PedidoGrupo(BaseModel):
    ids: list[str]
    ativo: bool


class PedidoPadrao(BaseModel):
    busca: str
    resposta: str


class PedidoRecomendar(BaseModel):
    conhecimentos: list[str] = []
    abreviacoes: list[str] = []
    sinonimos: list[str] = []


class PedidoLoja(BaseModel):
    addon: str | None = None   # id de um addon para já abrir a loja filtrada nele


class PedidoAtivar(BaseModel):
    ativo: bool


class PedidoRenomear(BaseModel):
    titulo: str = Field(min_length=1, max_length=120)


class PedidoLinguagem(BaseModel):
    # abreviacoes: termo + valor(expansão) | sinonimos: termo + valor(canônico)
    # intencoes:   termo(intenção) + valor(frase de exemplo)
    termo: str = Field(min_length=1)
    valor: str = Field(min_length=1)


TABELAS_LINGUAGEM = {"abreviacoes", "sinonimos", "intencoes"}


def criar_app(caminho_banco: str | Path | None = None) -> FastAPI:
    """Cria a aplicação. Receber o caminho do banco facilita os testes."""
    banco = Banco(caminho_banco or config.caminho_banco())
    assistente = Assistente(banco)

    app = FastAPI(title="Aprendiz", version=config.VERSAO,
                  description="API local do assistente pessoal Aprendiz.")
    app.state.banco = banco
    app.state.assistente = assistente
    app.state.ultimo_sinal = None  # atualizado pela interface a cada 10 s

    # ------------------------------------------------------------ interface
    app.mount("/static", StaticFiles(directory=config.PASTA_WEB), name="static")

    @app.get("/", include_in_schema=False)
    def pagina_inicial():
        return FileResponse(config.PASTA_WEB / "index.html")

    # ------------------------------------------------------------ geral
    @app.get("/api/status")
    def status():
        return {
            "app": config.NOME_APP,
            "versao": config.VERSAO,
            "conhecimentos": banco.contar_conhecimentos(),
            "conhecimentos_addons": banco.contar_conhecimentos(de_addons=True),
            "addons": len(banco.listar_addons()),
            "conversas": len(banco.listar_conversas()),
            "banco": banco.caminho,
            "loja_oficial": config.URL_LOJA_OFICIAL,
        }

    @app.post("/api/loja-oficial")
    def abrir_loja_oficial(pedido: PedidoLoja | None = None):
        """
        Abre a loja oficial no navegador PADRÃO do sistema. O endereço vem de
        config.URL_LOJA_OFICIAL e não pode ser trocado pela requisição: a
        interface só pede "abra a loja", nunca manda um endereço. É o único
        momento em que o app aciona a internet, e só quando o dono clica.

        Com {"addon": id} (recomendação da compreensão), a loja abre já
        filtrada naquele addon: o id só pode ter letras minúsculas, números e
        hífen, e vira apenas o parâmetro ?busca= do MESMO endereço oficial.
        """
        url = config.URL_LOJA_OFICIAL
        if pedido and pedido.addon:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", pedido.addon):
                raise HTTPException(400, "Id de addon inválido.")
            url += "?busca=" + quote(pedido.addon)
        try:
            aberto = webbrowser.open(url, new=2)
        except webbrowser.Error:
            aberto = False
        return {"aberto": bool(aberto), "url": url}

    @app.post("/api/sinal", include_in_schema=False)
    def sinal():
        app.state.ultimo_sinal = time.monotonic()
        return {"ok": True}

    @app.get("/api/algoritmos")
    def algoritmos():
        dados = listar_algoritmos()
        # O limiar exibido é o que está EM VIGOR (o dono ou um addon podem ter mudado).
        efetivas = assistente.configuracoes.efetivas()
        for a in dados["busca"]:
            chave = f"limiar.{a['nome']}"
            if chave in efetivas:
                a["limiar_padrao"], a["limiar"] = a["limiar"], efetivas[chave]["valor"]
        # Normas dos addons ativos: opções da configuração "revisao.norma".
        dados["normas"] = [{"nome": "", "titulo": "Automática"}] + [
            {"nome": n["id"], "titulo": n["nome"]} for n in assistente.normas_disponiveis()]
        return dados

    # ------------------------------------------------------------ revisão de texto
    @app.get("/api/normas")
    def normas():
        return assistente.normas_disponiveis()

    @app.post("/api/revisar")
    def revisar(pedido: PedidoRevisao):
        try:
            return assistente.revisar_texto(pedido.texto, pedido.norma)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro

    # ------------------------------------------------------------ chat
    # Rotas declaradas com "def" (e não "async def") rodam numa thread
    # separada; assim uma busca mais demorada não trava o servidor.
    @app.post("/api/chat")
    def chat(pedido: PedidoChat):
        try:
            return assistente.responder(pedido.mensagem, pedido.conversa_id,
                                        pedido.busca, pedido.resposta)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.post("/api/chat/fluxo")
    def chat_fluxo(pedido: PedidoChat):
        """
        O pipeline AO VIVO (2.4), para o Monitor. A resposta é NDJSON: um
        objeto JSON por linha, enviado assim que fica pronto.

            {"evento": "etapa", "indice": 0, "nome": "Normalização", "ms": 0.8, ...}
            {"evento": "etapa", "indice": 1, ...}
            {"evento": "fim", "resposta": {...o mesmo de /api/chat...}}
            {"evento": "erro", "mensagem": "..."}          (se algo falhar)

        O Assistente roda numa thread e avisa cada etapa por um "ouvinte"
        (Etapas.ouvinte), que coloca o evento numa fila; o gerador lê a fila e
        envia. É o padrão produtor-consumidor.
        """
        fila: queue.Queue = queue.Queue()

        def produzir() -> None:
            try:
                r = assistente.responder(pedido.mensagem, pedido.conversa_id, pedido.busca,
                                         pedido.resposta,
                                         ouvinte=lambda e: fila.put({"evento": "etapa", **e}))
                fila.put({"evento": "fim", "resposta": r})
            except ValueError as erro:
                fila.put({"evento": "erro", "mensagem": str(erro)})
            except Exception as erro:  # noqa: BLE001 — o cliente precisa saber que falhou
                fila.put({"evento": "erro", "mensagem": f"Erro interno: {erro}"})
            finally:
                fila.put(None)

        threading.Thread(target=produzir, daemon=True).start()

        def consumir():
            while (evento := fila.get()) is not None:
                yield json.dumps(evento, ensure_ascii=False, default=str) + "\n"

        return StreamingResponse(consumir(), media_type="application/x-ndjson")

    @app.get("/api/modelo")
    def modelo():
        """Ficha técnica (2.4): componentes, parâmetros por tipo, treino e ambiente."""
        return monitor.ficha_do_modelo(assistente)

    @app.post("/api/corrigir")
    def corrigir(pedido: PedidoCorrecao):
        try:
            return assistente.corrigir(pedido.mensagem_id, pedido.resposta_correta)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.post("/api/resetar")
    def resetar(pedido: PedidoReset):
        """
        Volta ao estado inicial. Antes de apagar qualquer coisa, salva uma
        cópia completa do banco em <pasta de dados>/backups/, para o caso de
        arrependimento (basta colocar a cópia no lugar do aprendiz.db).
        """
        if pedido.confirmacao != "RESETAR":
            raise HTTPException(400, 'Digite RESETAR para confirmar.')
        if not (pedido.conhecimentos or pedido.linguagem or pedido.conversas or pedido.addons
                or pedido.configuracoes):
            raise HTTPException(400, "Escolha pelo menos uma parte para resetar.")
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = banco.fazer_backup(
            Path(banco.caminho).parent / "backups" / f"aprendiz-{carimbo}.db")
        apagados = banco.resetar(pedido.conhecimentos, pedido.linguagem,
                                 pedido.conversas, pedido.addons, pedido.configuracoes)
        if pedido.addons and not pedido.linguagem:
            assistente.reindexar()  # sinônimos de addons sumiram: refaz os radicais
        return {"ok": True, "backup": str(backup), "apagados": apagados}

    # ------------------------------------------------------------ conversas
    @app.get("/api/conversas")
    def listar_conversas():
        return banco.listar_conversas()

    @app.get("/api/conversas/{conversa_id}/mensagens")
    def mensagens(conversa_id: str):
        if not banco.obter_conversa(conversa_id):
            raise HTTPException(404, "Conversa não encontrada.")
        return banco.listar_mensagens(conversa_id)

    @app.patch("/api/conversas/{conversa_id}")
    def renomear(conversa_id: str, pedido: PedidoRenomear):
        banco.renomear_conversa(conversa_id, pedido.titulo.strip())
        return {"ok": True}

    @app.delete("/api/conversas/{conversa_id}")
    def apagar_conversa(conversa_id: str):
        banco.remover_conversa(conversa_id)
        return {"ok": True}

    # ------------------------------------------------------------ conhecimento
    @app.get("/api/conhecimentos")
    def listar_conhecimentos(filtro: str = "", limite: int = 200, deslocamento: int = 0,
                             addon: str | None = None):
        return {
            "total": banco.contar_conhecimentos(),
            "itens": banco.listar_conhecimentos(filtro, limite, deslocamento, addon),
        }

    @app.post("/api/conhecimentos")
    def ensinar(pedido: PedidoConhecimento):
        return assistente.ensinar(pedido.conteudo, pergunta=pedido.pergunta)

    @app.put("/api/conhecimentos/{conhecimento_id}")
    def editar(conhecimento_id: str, pedido: PedidoConhecimento):
        atual = banco.obter_conhecimento(conhecimento_id)
        if not atual:
            raise HTTPException(404, "Conhecimento não encontrado.")
        tipo = "pergunta" if pedido.pergunta else (
            atual["tipo"] if atual["tipo"] != "pergunta" else "nota")
        return assistente.ensinar(pedido.conteudo, pergunta=pedido.pergunta, tipo=tipo,
                                  origem=atual["origem"], id=conhecimento_id)

    @app.delete("/api/conhecimentos/{conhecimento_id}")
    def remover(conhecimento_id: str):
        if not banco.remover_conhecimento(conhecimento_id):
            raise HTTPException(404, "Conhecimento não encontrado.")
        return {"ok": True}

    @app.post("/api/importar")
    def importar(pedido: PedidoImportacao):
        if not pedido.nome.lower().endswith((".txt", ".md")):
            raise HTTPException(400, "Nesta versão, só arquivos .txt e .md.")
        return {"trechos": assistente.importar_texto(pedido.nome, pedido.texto)}

    # ------------------------------------------------------------ addons
    @app.get("/api/addons")
    def listar_addons():
        return banco.listar_addons()

    def _bytes_do_addon(pedido: PedidoAddon) -> bytes:
        if not pedido.nome_arquivo.lower().endswith((".aprendiz", ".aprendiz-pacote")):
            raise HTTPException(400, "Escolha um arquivo de addon (.aprendiz ou .aprendiz-pacote).")
        try:
            return base64.b64decode(pedido.conteudo_base64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "Arquivo corrompido no envio.") from None

    @app.post("/api/addons/pacote/inspecionar")
    def inspecionar_pacote(pedido: PedidoAddon):
        """Pacote de addons da loja (2.2): o que vem nele, SEM instalar."""
        try:
            return assistente.inspecionar_pacote(_bytes_do_addon(pedido))
        except ErroAddon as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.post("/api/addons/pacote")
    def instalar_pacote(pedido: PedidoAddon):
        try:
            return {"resultado": assistente.instalar_pacote(_bytes_do_addon(pedido))}
        except ErroAddon as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.post("/api/addons/inspecionar")
    def inspecionar_addon(pedido: PedidoAddon):
        """Lê o arquivo SEM instalar: alimenta a tela de confirmação."""
        try:
            return assistente.inspecionar_addon(_bytes_do_addon(pedido))
        except ErroAddon as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.post("/api/addons")
    def instalar_addon(pedido: PedidoAddon):
        try:
            resultado = assistente.instalar_addon(_bytes_do_addon(pedido))
        except ErroAddon as erro:
            raise HTTPException(400, str(erro)) from erro
        addon = resultado["addon"]
        rec = (addon["manifesto"] or {}).get("recomendado")
        if pedido.usar_recomendacao and rec:
            try:
                assistente.usar_padrao(rec["busca"], rec["resposta"])
            except ValueError:
                pass  # algoritmo que não existe nesta versão: mantém o atual
        if pedido.ativar_grupo:
            grupo = next((g for g in assistente.grupos_de_addons()
                          if any(a["id"] == addon["id"] for a in g["addons"])), None)
            if grupo and grupo["chave"]:
                assistente.definir_addons_ativos([a["id"] for a in grupo["addons"]], True)
        return resultado

    @app.get("/api/addons/grupos")
    def grupos_de_addons():
        """Addons agrupados pelo padrão de busca e resposta que recomendam."""
        return assistente.grupos_de_addons()

    @app.post("/api/addons/grupo")
    def ativar_varios(pedido: PedidoGrupo):
        """Ativa ou desativa vários addons de uma vez (ex.: um grupo inteiro)."""
        return {"alterados": assistente.definir_addons_ativos(pedido.ids, pedido.ativo)}

    @app.put("/api/padrao")
    def usar_padrao(pedido: PedidoPadrao):
        """Define de uma vez os algoritmos padrão de busca e de resposta."""
        try:
            assistente.usar_padrao(pedido.busca, pedido.resposta)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        return assistente.configuracoes.descrever()

    # ------------------------------------------------------------ exportação
    @app.get("/api/exportar")
    def previa_exportacao():
        return exportacao.previa(banco)

    @app.post("/api/exportar/recomendar")
    def recomendar_exportacao(pedido: PedidoRecomendar):
        """Refaz o teste de algoritmos só com os itens marcados."""
        dados = exportacao.previa(banco, recomendar=False)
        itens = [k for k in dados["conhecimentos"] if k["id"] in set(pedido.conhecimentos)]
        linguagem = {t: {e["termo"]: e["valor"] for e in dados["linguagem"][t]
                         if e["termo"] in set(getattr(pedido, t))}
                     for t in ("abreviacoes", "sinonimos")}
        return exportacao.recomendar_para(itens, linguagem)

    @app.post("/api/exportar")
    def exportar(pedido: PedidoExportacao):
        try:
            # model_dump() é do Pydantic 2; .dict() mantém compatibilidade com o 1.
            escolha = pedido.model_dump() if hasattr(pedido, "model_dump") else pedido.dict()
            nome, dados = exportacao.exportar(banco, escolha)
        except ErroAddon as erro:
            raise HTTPException(400, str(erro)) from erro
        return Response(dados, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{nome}"'})

    # ------------------------------------------------------------ configurações
    @app.get("/api/configuracoes")
    def listar_configuracoes():
        return assistente.configuracoes.descrever()

    @app.put("/api/configuracoes/{chave}")
    def definir_configuracao(chave: str, pedido: PedidoConfiguracao):
        try:
            assistente.configuracoes.definir(chave, pedido.valor)
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        return assistente.configuracoes.descrever()

    @app.delete("/api/configuracoes/{chave}")
    def remover_configuracao(chave: str):
        """Volta a chave ao valor do addon ativo ou ao padrão."""
        try:
            assistente.configuracoes.remover(chave)
        except ValueError as erro:
            raise HTTPException(404, str(erro)) from erro
        return assistente.configuracoes.descrever()

    @app.patch("/api/addons/{addon_id}")
    def ativar_addon(addon_id: str, pedido: PedidoAtivar):
        try:
            return assistente.definir_addon_ativo(addon_id, pedido.ativo)
        except ValueError as erro:
            raise HTTPException(404, str(erro)) from erro

    @app.delete("/api/addons/{addon_id}")
    def remover_addon(addon_id: str):
        if not assistente.remover_addon(addon_id):
            raise HTTPException(404, "Addon não encontrado.")
        return {"ok": True}

    # ------------------------------------------------------------ linguagem
    @app.get("/api/linguagem")
    def linguagem():
        return {
            # Só as entradas do dono (as de addons são geridas na tela de addons).
            "abreviacoes": [{"termo": t, "valor": v}
                            for t, v in banco.mapa_abreviacoes(incluir_addons=False).items()],
            "sinonimos": [{"termo": t, "valor": v}
                          for t, v in banco.mapa_sinonimos(incluir_addons=False).items()],
            "intencoes": [{"id": e["id"], "termo": e["intencao"], "valor": e["frase"]}
                          for e in banco.exemplos_intencoes()],
            "stopwords": sorted(banco.lista_stopwords(incluir_addons=False)),
            # 1.0: o que vem dos addons (só leitura, com a origem) e os conflitos
            # entre eles, que o dono resolve escolhendo uma das opções.
            "de_addons": {t: banco.linguagem_de_addons(t) for t in ("abreviacoes", "sinonimos")},
            "conflitos": banco.conflitos_linguagem(),
        }

    @app.post("/api/linguagem/{tabela}")
    def adicionar_linguagem(tabela: str, pedido: PedidoLinguagem):
        if tabela not in TABELAS_LINGUAGEM:
            raise HTTPException(404, "Tabela desconhecida.")
        # Termos são guardados normalizados (minúsculas, sem acento), que é
        # como o normalizador os procura.
        termo, valor = normalizar(pedido.termo), normalizar(pedido.valor)
        if not termo or not valor:
            raise HTTPException(400, "Use letras ou números.")
        if tabela == "abreviacoes":
            banco.salvar_abreviacao(termo, valor)
        elif tabela == "sinonimos":
            banco.salvar_sinonimo(termo, valor)
        else:
            banco.salvar_exemplo_intencao(termo.replace(" ", "_"), valor)
        # Abreviações e sinônimos mudam os radicais → a base precisa ser reindexada.
        reindexados = assistente.reindexar() if tabela != "intencoes" else 0
        return {"ok": True, "reindexados": reindexados}

    @app.delete("/api/linguagem/{tabela}/{chave}")
    def remover_linguagem(tabela: str, chave: str):
        if tabela == "abreviacoes":
            banco.remover_abreviacao(chave)
        elif tabela == "sinonimos":
            banco.remover_sinonimo(chave)
        elif tabela == "intencoes":
            banco.remover_exemplo_intencao(int(chave))
        else:
            raise HTTPException(404, "Tabela desconhecida.")
        reindexados = assistente.reindexar() if tabela != "intencoes" else 0
        return {"ok": True, "reindexados": reindexados}

    return app
