import customtkinter as ctk
from gui.interface import App
from data.conexao import criar_tabela, migrar

def main():
    criar_tabela()
    migrar()
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()