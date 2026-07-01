import matplotlib.pyplot as plt
from waste_minimization_mesa.model import run_scenario

def plot_black_and_white():
    # 1. Executa os cenários programaticamente
    control = run_scenario(
        name="Sem Desconto", days=30, db_url="sqlite:///grafico_control.db", 
        num_consumers=20, pricing_enabled=False, seed=42
    )
    discounted = run_scenario(
        name="Com Desconto", days=30, db_url="sqlite:///grafico_discount.db", 
        num_consumers=20, pricing_enabled=True, seed=42
    )

    # 2. Extrai os dados
    ticks = [m.tick for m in control.metrics]
    
    estoque_control = [m.total_stock for m in control.metrics]
    estoque_discount = [m.total_stock for m in discounted.metrics]
    
    lucro_control = [m.profit for m in control.metrics]
    lucro_discount = [m.profit for m in discounted.metrics]

    # 3. Configura a plotagem estrita em Preto e Branco
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['text.color'] = 'black'
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Gráfico 1: Dinâmica de Estoque (Escoamento)
    # Linha contínua para Controle, Linha tracejada pontilhada para o Multiagente
    ax1.plot(ticks, estoque_control, color='black', linestyle='-', linewidth=2, label='Cenario Tradicional (Sem IA)')
    ax1.plot(ticks, estoque_discount, color='black', linestyle='--', linewidth=2, label='Cenario Multiagente (Proativo)')
    ax1.set_title('Volume de Estoque Fisico ao Longo do Tempo', fontweight='bold')
    ax1.set_ylabel('Unidades em Estoque')
    ax1.legend(edgecolor='black')

    # Gráfico 2: Evolução do Lucro (O Trade-off)
    ax2.plot(ticks, lucro_control, color='black', linestyle='-', linewidth=2, label='Lucro Cenario Tradicional')
    ax2.plot(ticks, lucro_discount, color='black', linestyle='--', linewidth=2, label='Lucro Cenario Multiagente')
    ax2.set_title('Lucro Diario Liquido', fontweight='bold')
    ax2.set_xlabel('Dias (Ticks de Simulacao)')
    ax2.set_ylabel('Lucro (R$)')
    ax2.legend(edgecolor='black')

    # Linha zero absoluta (preta) para marcar a área de prejuízo no eixo Y do gráfico 2
    ax2.axhline(0, color='black', linestyle='-', linewidth=1)

    plt.tight_layout()
    plt.savefig('graficos_resultados.png', dpi=300, bbox_inches='tight')
    print("Gráfico 'graficos_resultados.png' gerado com sucesso.")

if __name__ == "__main__":
    plot_black_and_white()