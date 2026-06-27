import matplotlib.pyplot as plt
from waste_minimization_mesa.model import run_scenario

def plot_demand_vs_fixed():
    print("Executando simulação de Reposição Fixa...")
    fixa = run_scenario(
        name="Fixa", days=40, db_url="sqlite:///grafico_fixa.db", 
        num_consumers=10, pricing_enabled=True, seed=42, restock_strategy="fixed"
    )
    
    print("Executando simulação de Reposição por Demanda...")
    demanda = run_scenario(
        name="Demanda", days=40, db_url="sqlite:///grafico_demanda.db", 
        num_consumers=10, pricing_enabled=True, seed=42, restock_strategy="demand"
    )

    ticks = [m.tick for m in fixa.metrics]
    estoque_fixa = [m.total_stock for m in fixa.metrics]
    estoque_demanda = [m.total_stock for m in demanda.metrics]
    
    # Acumulando o desperdício ao longo do tempo para ver o impacto da estratégia
    desperdicio_fixa_acc = []
    desperdicio_demanda_acc = []
    acc_fixa = 0
    acc_dem = 0
    
    for m_f, m_d in zip(fixa.metrics, demanda.metrics):
        acc_fixa += m_f.waste_units
        acc_dem += m_d.waste_units
        desperdicio_fixa_acc.append(acc_fixa)
        desperdicio_demanda_acc.append(acc_dem)

    # Configuração estrita de Preto e Branco (sem tons de cinza)
    plt.rcParams['figure.facecolor'] = 'white'
    plt.rcParams['axes.facecolor'] = 'white'
    plt.rcParams['axes.edgecolor'] = 'black'
    plt.rcParams['axes.labelcolor'] = 'black'
    plt.rcParams['xtick.color'] = 'black'
    plt.rcParams['ytick.color'] = 'black'
    plt.rcParams['text.color'] = 'black'
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Gráfico 1: Variação de Estoque
    ax1.plot(ticks, estoque_fixa, color='black', linestyle='-', linewidth=2, label='Reposicao Fixa (A cada 5 dias)')
    ax1.plot(ticks, estoque_demanda, color='black', linestyle='--', linewidth=2, label='Reposicao por Demanda (Gatilho: <= 15)')
    ax1.axhline(15, color='black', linestyle=':', linewidth=1, label='Ponto de Pedido (Threshold)')
    ax1.set_title('Comportamento do Estoque Fisico', fontweight='bold')
    ax1.set_ylabel('Unidades em Estoque')
    ax1.legend(edgecolor='black')

    # Gráfico 2: Desperdício Acumulado
    ax2.plot(ticks, desperdicio_fixa_acc, color='black', linestyle='-', linewidth=2, label='Desperdicio - Fixa')
    ax2.plot(ticks, desperdicio_demanda_acc, color='black', linestyle='--', linewidth=2, label='Desperdicio - Demanda')
    ax2.set_title('Desperdicio Acumulado de Pereciveis', fontweight='bold')
    ax2.set_xlabel('Dias (Ticks de Simulacao)')
    ax2.set_ylabel('Unidades Descartadas')
    ax2.legend(edgecolor='black')

    plt.tight_layout()
    plt.savefig('graficos_estrategias.png', dpi=300, bbox_inches='tight')
    print("Gráfico 'graficos_estrategias.png' gerado com sucesso!")

if __name__ == "__main__":
    plot_demand_vs_fixed()