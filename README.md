# ANTICIPA · Generador de datos sintéticos (v0.1)

Genera una cartera **ficticia** de microempresarios para entrenar y probar ANTICIPA, el sistema de alerta temprana de deterioro de pago (Cajathon, Caja Trujillo, Eje 3). Ningún dato corresponde a personas reales.

## Uso

```bash
pip install numpy pandas
python generador.py --clientes 5000 --meses 36 --semilla 42 --salida datos
```

Con los valores por defecto tarda unos 20 segundos y produce 6 archivos CSV (unos 24 MB). La misma semilla siempre genera los mismos datos.

## Qué simula

- **Clientes:** 6 rubros (bodega, mercado, transporte, agro, taller, servicios) en 4 zonas de La Libertad. En Virú predomina el agro.
- **Créditos:** cuota fija, plazos de 12, 18 o 24 meses y renovaciones cuando el cliente termina al día.
- **Pagos:** días de anticipación o retraso frente al vencimiento, pagos parciales y días de atraso al cierre de cada mes.
- **Ahorros:** depósitos, retiros y saldo mensual. Solo el 65 % de los clientes tiene cuenta, como en la realidad.
- **Deuda en otras entidades (tipo RCC):** saldo y número de entidades, con fecha de disponibilidad 45 días después del cierre de mes.
- **Estacionalidad por rubro:** en temporada baja los clientes estacionales pagan más tarde, pero sin caer en mora.
- **Evento tipo El Niño:** de marzo a junio de 2025, en el agro y el transporte de Virú. Baja las ventas y, según la exposición de cada cliente, su capacidad de pago. Una parte entra en deterioro después del evento.

### Perfiles

| Perfil | Proporción | Comportamiento |
|---|---|---|
| estable | 72 % | Paga antes del vencimiento; no cae en mora |
| estacional | 10 % | Estacionalidad doble; paga tarde en temporada baja sin superar 30 días |
| deterioro | 7 % | Deterioro gradual desde un mes al azar; el 30 % se recupera sin mora (casos difíciles) |
| anomalia | 5 % | Un solo mes malo que se recupera; no debe generar alerta |
| nuevo | 6 % | Crédito en los últimos 3 meses; historial insuficiente |
| deterioro_fen | variable | Clientes afectados por El Niño que entran en deterioro después del evento |

Resultado con la semilla 42: alrededor de 6 % de clientes supera 30 días de atraso. En promedio, las señales empiezan unos 5 meses antes.

## Archivos generados

| Archivo | Una fila por | Campos principales |
|---|---|---|
| `clientes.csv` | cliente | id_cliente, nombre_ficticio, rubro, zona, tiene_cuenta_ahorro, antiguedad_meses, ventas_base_mensual, perfil_simulado*, afectado_fen*, eval_periodo_inicio_deterioro* |
| `creditos.csv` | crédito | id_credito, id_cliente, monto, plazo_meses, cuota, dia_vencimiento, fecha_desembolso |
| `pagos.csv` | cuota | id_credito, id_cliente, periodo, fecha_vencimiento, fecha_pago, monto_cuota, monto_pagado, pago_parcial, dias_atraso_cierre |
| `ahorros_mensual.csv` | cliente y mes | id_cliente, periodo, depositos, retiros, saldo_fin_mes |
| `rcc_mensual.csv` | cliente y mes | id_cliente, periodo, deuda_otras_entidades, num_entidades, fecha_disponible |
| `eventos_deterioro.csv` | cliente | id_cliente, periodo_primer_atraso_30 |

\* **Verdad de terreno:** sirve solo para evaluar el modelo. Nunca debe usarse como variable de entrada, porque sería fuga de información.

## Reglas para quien construya el modelo

- La etiqueta es "supera 30 días de atraso dentro de los próximos 60 días". Se obtiene de `pagos.dias_atraso_cierre` o de `eventos_deterioro`.
- Usar solo información disponible a cada fecha. Por ejemplo, el RCC de un mes recién se conoce en `fecha_disponible`.
- Si un cliente no tiene cuenta de ahorros, sus variables quedan vacías. "Sin dato" no es una señal negativa.

## Pendiente (próximas versiones)

- Calibrar las proporciones con los insumos agregados que comparta la Caja.
- Agregar la evaluación crediticia del asesor (ingresos, egresos y cobertura de cuota).
- Parametrizar los eventos externos desde un archivo de configuración.
- Acelerar la generación para carteras más grandes.
