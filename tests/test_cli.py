from app.cli import cmd_historico, _snapshots_todos


def test_cmd_historico_diaria(repo_com_dados, capsys):
    args = type("A", (), {"granularidade": "diaria"})()
    cmd_historico(args)
    out = capsys.readouterr().out
    assert "Evolução do patrimônio" in out
    assert "R$ 1.000,00" in out
    assert "R$ 1.200,00" in out


def test_cmd_historico_mensal(repo_com_dados, capsys):
    args = type("A", (), {"granularidade": "mensal"})()
    cmd_historico(args)
    out = capsys.readouterr().out
    assert "Evolução mensal" in out
    # valores dependem do agrupamento de evolucao_mensal — valide formatos:
    assert "R$" in out


def test_cmd_historico_acumulado(repo_com_dados, capsys):
    args = type("A", (), {"granularidade": "acumulado"})()
    cmd_historico(args)
    out = capsys.readouterr().out
    assert "Crescimento acumulado" in out
    assert "+" in out  # 20% no fim


def test_cmd_historico_sem_dados(repo, capsys):
    args = type("A", (), {"granularidade": "mensal"})()
    cmd_historico(args)
    out = capsys.readouterr().out
    assert "(sem dados)" in out


def test_snapshots_todos_pega_intervalo_aberto(repo_com_dados, monkeypatch):
    """_snapshots_todos usa date.min como início — cobre tudo que existe."""
    import app.cli as cli
    monkeypatch.setattr(cli, "get_connection", lambda *a, **kw: repo_com_dados._conn)
    snaps = cli._snapshots_todos()
    assert len(snaps) == 3


def test_main_historico_integrado(repo_com_dados, monkeypatch, capsys):
    """Cobre o parser, subcomandos e dispatch do main()."""
    import app.cli as cli
    monkeypatch.setattr(cli, "get_connection", lambda *a, **kw: repo_com_dados._conn)
    monkeypatch.setattr("sys.argv", ["open-wealth", "historico", "-g", "diaria"])
    cli.main()
    out = capsys.readouterr().out
    assert "Evolução do patrimônio" in out


def test_main_granularidade_default(repo, monkeypatch, capsys):
    """Sem -g, cai em 'mensal' (default) e o parser roda."""
    import app.cli as cli
    monkeypatch.setattr(cli, "get_connection", lambda *a, **kw: repo._conn)
    monkeypatch.setattr("sys.argv", ["open-wealth", "historico"])
    cli.main()
    out = capsys.readouterr().out
    assert "Evolução mensal" in out
