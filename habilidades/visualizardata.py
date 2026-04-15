import datetime
def executar():
    hoje = datetime.datetime.now()
    print(f"Data atual: {hoje.strftime('%d/%m/%Y')} - {hoje.strftime('%A')}")
