"""Graficos animados (ECharts) com glow, tema dark/light e crosshair sincronizado."""
import json

from theme import get_palette

ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"


def _frame_reset() -> str:
    """O iframe herda a altura definida via CSS pelo tema (responsiva a vh); aqui garantimos
    que a arvore html/body/wrap dentro dele ocupe 100% dessa altura, em vez de um px fixo."""
    return "<style>html,body{margin:0;height:100%;overflow:hidden;}</style>"


def trend_and_conversions(dates: list[str], gasto: list[float], conversoes: list[int], theme: str) -> str:
    """Duas series de mesmo eixo x, sincronizadas por crosshair, sem eixo duplo (uma metrica por grafico)."""
    p = get_palette(theme)

    return f"""
    {_frame_reset()}
    <div id="wrap-trend" style="width:100%;height:100%;display:flex;flex-direction:column;">
      <div id="chart-gasto" style="width:100%;flex:0 0 65%;"></div>
      <div id="chart-conv" style="width:100%;flex:0 0 35%;"></div>
    </div>
    <script src="{ECHARTS_CDN}"></script>
    <script>
    (function() {{
      const dates = {json.dumps(dates)};
      const gasto = {json.dumps(gasto)};
      const conv = {json.dumps(conversoes)};
      const p = {json.dumps(p)};

      const gastoDom = document.getElementById('chart-gasto');
      const convDom = document.getElementById('chart-conv');
      const gastoChart = echarts.init(gastoDom, null, {{ renderer: 'svg' }});
      const convChart = echarts.init(convDom, null, {{ renderer: 'svg' }});

      const gastoOption = {{
        backgroundColor: 'transparent',
        animationDuration: 1400,
        animationEasing: 'cubicOut',
        grid: {{ left: 56, right: 20, top: 24, bottom: 6, containLabel: false }},
        tooltip: {{
          trigger: 'axis',
          backgroundColor: p.surface_2,
          borderColor: p.border,
          textStyle: {{ color: p.text_primary }},
          axisPointer: {{ type: 'line', lineStyle: {{ color: p.series_blue, opacity: 0.4 }} }},
          valueFormatter: (v) => 'R$ ' + Number(v).toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})
        }},
        xAxis: {{
          type: 'category', data: dates, boundaryGap: false,
          axisLine: {{ lineStyle: {{ color: p.baseline }} }},
          axisLabel: {{ color: p.muted, fontSize: 11 }},
          axisTick: {{ show: false }},
          splitLine: {{ show: false }}
        }},
        yAxis: {{
          type: 'value',
          axisLabel: {{ color: p.muted, fontSize: 11, formatter: (v) => 'R$ ' + v.toLocaleString('pt-BR') }},
          splitLine: {{ lineStyle: {{ color: p.gridline }} }}
        }},
        series: [{{
          name: 'Gasto',
          type: 'line',
          data: gasto,
          smooth: 0.35,
          symbol: 'circle',
          symbolSize: 6,
          showSymbol: false,
          lineStyle: {{ width: 3, color: p.series_blue, shadowColor: p.glow_blue, shadowBlur: 18 }},
          itemStyle: {{ color: p.series_blue, borderColor: p.surface, borderWidth: 2 }},
          areaStyle: {{
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              {{ offset: 0, color: p.glow_blue }},
              {{ offset: 1, color: 'rgba(0,0,0,0)' }}
            ])
          }},
          emphasis: {{ focus: 'series' }}
        }}]
      }};

      const convOption = {{
        backgroundColor: 'transparent',
        animationDuration: 1400,
        animationDelay: 200,
        animationEasing: 'cubicOut',
        grid: {{ left: 56, right: 20, top: 10, bottom: 22, containLabel: false }},
        tooltip: {{
          trigger: 'axis',
          backgroundColor: p.surface_2,
          borderColor: p.border,
          textStyle: {{ color: p.text_primary }},
          axisPointer: {{ type: 'line', lineStyle: {{ color: p.series_aqua, opacity: 0.4 }} }}
        }},
        xAxis: {{
          type: 'category', data: dates, boundaryGap: true,
          axisLine: {{ lineStyle: {{ color: p.baseline }} }},
          axisLabel: {{ color: p.muted, fontSize: 10, interval: Math.floor(dates.length / 8) }},
          axisTick: {{ show: false }},
          splitLine: {{ show: false }}
        }},
        yAxis: {{
          type: 'value',
          axisLabel: {{ color: p.muted, fontSize: 11 }},
          splitLine: {{ lineStyle: {{ color: p.gridline }} }}
        }},
        series: [{{
          name: 'Conversões',
          type: 'bar',
          data: conv,
          barMaxWidth: 14,
          itemStyle: {{
            color: p.series_aqua,
            borderRadius: [4, 4, 0, 0],
            shadowColor: p.glow_aqua,
            shadowBlur: 10
          }},
          emphasis: {{ focus: 'series', itemStyle: {{ color: p.series_aqua, shadowBlur: 20 }} }}
        }}]
      }};

      gastoChart.setOption(gastoOption);
      convChart.setOption(convOption);
      echarts.connect([gastoChart, convChart]);

      window.addEventListener('resize', function() {{
        gastoChart.resize();
        convChart.resize();
      }});
    }})();
    </script>
    """


def funnel_chart(impressoes: int, cliques: int, conversoes: int, theme: str) -> str:
    p = get_palette(theme)
    ramp_light = ["#c4b5fd", "#7c3aed", "#4c1d95"]
    ramp_dark = ["#c4b5fd", "#8b5cf6", "#5b21b6"]
    cores = ramp_light if theme == "light" else ramp_dark

    data = [
        {"name": "Impressões", "value": impressoes},
        {"name": "Cliques", "value": cliques},
        {"name": "Conversões", "value": conversoes},
    ]

    return f"""
    {_frame_reset()}
    <div id="chart-funnel" style="width:100%;height:100%;"></div>
    <script src="{ECHARTS_CDN}"></script>
    <script>
    (function() {{
      const p = {json.dumps(p)};
      const cores = {json.dumps(cores)};
      const data = {json.dumps(data)};

      const dom = document.getElementById('chart-funnel');
      const chart = echarts.init(dom, null, {{ renderer: 'svg' }});

      const option = {{
        backgroundColor: 'transparent',
        animationDuration: 1200,
        animationEasing: 'cubicOut',
        tooltip: {{
          trigger: 'item',
          backgroundColor: p.surface_2,
          borderColor: p.border,
          textStyle: {{ color: p.text_primary }},
          formatter: (params) => params.name + ': ' + params.value.toLocaleString('pt-BR') + ' (' + params.percent.toFixed(1) + '%)'
        }},
        legend: {{ show: true, bottom: 0, textStyle: {{ color: p.text_secondary, fontSize: 12 }} }},
        series: [{{
          type: 'funnel',
          left: '8%', right: '8%', top: 10, bottom: 40,
          minSize: '30%', maxSize: '100%',
          gap: 3,
          label: {{
            show: true, position: 'inside', color: '#ffffff',
            fontWeight: 700, fontSize: 13,
            formatter: (p2) => p2.name + '\\n' + p2.value.toLocaleString('pt-BR')
          }},
          itemStyle: {{
            borderColor: p.surface, borderWidth: 2,
            shadowBlur: 14, shadowColor: p.glow_blue
          }},
          emphasis: {{ label: {{ fontSize: 15 }} }},
          data: data.map((d, i) => ({{ ...d, itemStyle: {{ color: cores[i] }} }}))
        }}]
      }};

      chart.setOption(option);
      window.addEventListener('resize', () => chart.resize());
    }})();
    </script>
    """


def campaign_bar_chart(campanhas: list[str], gastos: list[float], cpas: list[float], cpa_medio: float, theme: str) -> str:
    p = get_palette(theme)

    ordenado = sorted(zip(campanhas, gastos, cpas), key=lambda x: x[1])
    nomes = [x[0] for x in ordenado]
    valores = [round(x[1], 2) for x in ordenado]
    cpa_vals = [round(x[2], 2) for x in ordenado]
    cores = [p["good"] if c <= cpa_medio else p["critical"] for c in cpa_vals]

    return f"""
    {_frame_reset()}
    <div id="chart-campanhas" style="width:100%;height:100%;"></div>
    <script src="{ECHARTS_CDN}"></script>
    <script>
    (function() {{
      const p = {json.dumps(p)};
      const nomes = {json.dumps(nomes)};
      const valores = {json.dumps(valores)};
      const cores = {json.dumps(cores)};

      const dom = document.getElementById('chart-campanhas');
      const chart = echarts.init(dom, null, {{ renderer: 'svg' }});

      const option = {{
        backgroundColor: 'transparent',
        animationDuration: 1200,
        animationEasing: 'cubicOut',
        grid: {{ left: 10, right: 70, top: 10, bottom: 10, containLabel: true }},
        tooltip: {{
          trigger: 'axis',
          axisPointer: {{ type: 'shadow' }},
          backgroundColor: p.surface_2,
          borderColor: p.border,
          textStyle: {{ color: p.text_primary }},
          formatter: (params) => {{
            const d = params[0];
            return d.name + '<br/>Gasto: R$ ' + d.value.toLocaleString('pt-BR', {{minimumFractionDigits:2}});
          }}
        }},
        xAxis: {{
          type: 'value',
          axisLabel: {{ color: p.muted, fontSize: 11, formatter: (v) => 'R$ ' + v.toLocaleString('pt-BR') }},
          splitLine: {{ lineStyle: {{ color: p.gridline }} }}
        }},
        yAxis: {{
          type: 'category', data: nomes,
          axisLine: {{ lineStyle: {{ color: p.baseline }} }},
          axisLabel: {{ color: p.text_secondary, fontSize: 12 }}
        }},
        series: [{{
          type: 'bar',
          data: valores.map((v, i) => ({{
            value: v,
            itemStyle: {{ color: cores[i], borderRadius: [0, 6, 6, 0], shadowBlur: 8, shadowColor: cores[i] }}
          }})),
          barMaxWidth: 22,
          label: {{
            show: true, position: 'right', color: p.text_primary, fontSize: 12, fontWeight: 600,
            formatter: (d) => 'R$ ' + d.value.toLocaleString('pt-BR')
          }}
        }}]
      }};

      chart.setOption(option);
      window.addEventListener('resize', () => chart.resize());
    }})();
    </script>
    """
