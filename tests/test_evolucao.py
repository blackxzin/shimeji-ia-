"""Auto-modificação é a função mais perigosa: cada trava precisa de teste."""

import os

import pytest

from shimeji import evolucao
from shimeji.evolucao import ErroDeEvolucao, aplicar_melhoria, inserir_bloco, montar_bloco, sanitizar_nome

ARQUIVO_EXEMPLO = 'class Coisa:\n    def a(self):\n        pass\n\n\nif __name__ == "__main__":\n    Coisa()\n'


@pytest.fixture
def arquivo_alvo(tmp_path):
    caminho = tmp_path / "alvo.py"
    caminho.write_text(ARQUIVO_EXEMPLO, encoding="utf-8")
    return str(caminho)


@pytest.mark.parametrize("bruto, esperado", [
    ("Minha Função!", "minha_funcao"),
    ("cache de notas", "cache_de_notas"),
    ("__init__", "init"),
])
def test_sanitiza_nomes(bruto, esperado):
    assert sanitizar_nome(bruto) == esperado


@pytest.mark.parametrize("nome", ["", "   ", "123", "!!!"])
def test_nome_invalido_e_recusado(nome):
    with pytest.raises(ErroDeEvolucao):
        sanitizar_nome(nome)


@pytest.mark.parametrize("codigo", [
    'os.system("rm -rf /")',
    '__import__("os")',
    'exec("codigo")',
    'eval("1+1")',
    "subprocess.run(['ls'])",
    'shutil.rmtree("/")',
    'open("/etc/passwd", "w")',
    "socket.socket()",
])
def test_recusa_construcoes_perigosas(codigo):
    """A IA não pode transformar 'melhoria' em execução arbitrária."""
    with pytest.raises(ErroDeEvolucao, match="proibida"):
        montar_bloco("metodo", codigo)


def test_recusa_sintaxe_invalida():
    with pytest.raises(ErroDeEvolucao, match="sintaxe"):
        montar_bloco("metodo", "self.x = (1 + ")


def test_recusa_bloco_vazio():
    with pytest.raises(ErroDeEvolucao):
        montar_bloco("metodo", "   ;  ")


def test_bloco_valido_e_indentado():
    bloco = montar_bloco("somar", "self.total = 1; self.total += 1")
    assert "    def somar(self):" in bloco
    assert "        self.total = 1" in bloco


def test_insere_antes_do_ponto_de_entrada():
    resultado = inserir_bloco(ARQUIVO_EXEMPLO, "\n    def nova(self):\n        pass\n")
    assert resultado.index("def nova") < resultado.index('if __name__')


def test_desligada_por_padrao(arquivo_alvo):
    """Regressão: a versão anterior reescrevia o próprio código sem pedir nada."""
    with pytest.raises(ErroDeEvolucao, match="desligada"):
        aplicar_melhoria(arquivo_alvo, "nova", "pass", permitido=False)
    assert open(arquivo_alvo, encoding="utf-8").read() == ARQUIVO_EXEMPLO


def test_aplica_melhoria_valida(arquivo_alvo, monkeypatch, tmp_path):
    monkeypatch.setattr(evolucao, "ARQUIVO_MELHORIAS", str(tmp_path / "log.jsonl"))
    nome = aplicar_melhoria(arquivo_alvo, "Contar Coisas", "self.total = 0", permitido=True)

    conteudo = open(arquivo_alvo, encoding="utf-8").read()
    assert nome == "contar_coisas"
    assert "def contar_coisas(self):" in conteudo
    compile(conteudo, arquivo_alvo, "exec")  # o arquivo resultante precisa compilar


def test_cria_backup_antes_de_gravar(arquivo_alvo, monkeypatch, tmp_path):
    monkeypatch.setattr(evolucao, "ARQUIVO_MELHORIAS", str(tmp_path / "log.jsonl"))
    aplicar_melhoria(arquivo_alvo, "nova", "self.x = 1", permitido=True)
    backups = [nome for nome in os.listdir(tmp_path) if ".backup_" in nome]
    assert len(backups) == 1
    assert open(os.path.join(tmp_path, backups[0]), encoding="utf-8").read() == ARQUIVO_EXEMPLO


def test_registra_no_historico(arquivo_alvo, monkeypatch, tmp_path):
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(evolucao, "ARQUIVO_MELHORIAS", str(log))
    aplicar_melhoria(arquivo_alvo, "nova", "self.x = 1", permitido=True)
    assert '"funcao": "nova"' in log.read_text(encoding="utf-8")


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroDeEvolucao, match="não encontrado"):
        aplicar_melhoria(str(tmp_path / "fantasma.py"), "n", "pass", permitido=True)


def test_nao_deixa_temporarios_para_tras(arquivo_alvo, monkeypatch, tmp_path):
    monkeypatch.setattr(evolucao, "ARQUIVO_MELHORIAS", str(tmp_path / "log.jsonl"))
    aplicar_melhoria(arquivo_alvo, "nova", "self.x = 1", permitido=True)
    assert not [nome for nome in os.listdir(tmp_path) if nome.endswith((".tmp", ".pyc"))]
