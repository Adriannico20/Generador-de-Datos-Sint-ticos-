"""
ANTICIPA - Generador de datos sinteticos de cartera MYPE (v0.1)

Crea una cartera ficticia de microempresarios con historia mensual:
clientes, creditos con cronograma, pagos, ahorros, deuda en otras
entidades (tipo RCC, con desfase) y eventos de deterioro (> 30 dias).

Ningun dato corresponde a personas reales. Reproducible con semilla.

Uso:
    python generador.py --clientes 5000 --meses 36 --semilla 42 --salida datos
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Parametros del mundo simulado
# ---------------------------------------------------------------------------

RUBROS = ["bodega", "mercado", "transporte", "agro", "taller", "servicios"]

# Ventas mensuales base (S/) por rubro: mediana aproximada
VENTAS_BASE = {
    "bodega": 9000, "mercado": 7000, "transporte": 8000,
    "agro": 10000, "taller": 7500, "servicios": 6000,
}

# Estacionalidad: multiplicador por mes calendario (1..12)
ESTACIONALIDAD = {
    "bodega":     [0.90, 0.90, 1.05, 1.00, 1.00, 1.00, 1.05, 1.00, 1.00, 1.00, 1.00, 1.25],
    "mercado":    [0.85, 0.90, 1.00, 1.00, 1.00, 1.00, 1.10, 1.00, 1.00, 1.00, 1.00, 1.30],
    "transporte": [0.95, 0.90, 0.95, 1.00, 1.00, 1.00, 1.10, 1.05, 1.00, 1.00, 1.00, 1.10],
    "agro":       [0.70, 0.70, 0.75, 1.00, 1.00, 1.00, 1.10, 1.10, 1.10, 1.30, 1.30, 1.25],
    "taller":     [0.95, 0.95, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.10],
    "servicios":  [0.85, 0.85, 1.00, 1.00, 1.00, 1.00, 1.05, 1.00, 1.00, 1.00, 1.00, 1.15],
}

ZONAS = ["Trujillo Centro", "El Porvenir", "La Esperanza", "Viru"]
PROB_ZONA = [0.30, 0.25, 0.25, 0.20]
# Mezcla de rubros por zona (en Viru predomina el agro)
MEZCLA_RUBRO = {
    "Trujillo Centro": [0.25, 0.25, 0.15, 0.02, 0.15, 0.18],
    "El Porvenir":     [0.30, 0.25, 0.15, 0.02, 0.18, 0.10],
    "La Esperanza":    [0.30, 0.22, 0.18, 0.03, 0.15, 0.12],
    "Viru":            [0.15, 0.10, 0.15, 0.45, 0.08, 0.07],
}

# Perfiles de comportamiento y su proporcion
PERFILES = ["estable", "estacional", "deterioro", "anomalia", "nuevo"]
PROB_PERFIL = [0.72, 0.10, 0.07, 0.05, 0.06]

# Evento tipo Fenomeno El Nino: lluvias que golpean agro y transporte en Viru
FEN = {
    "inicio": "2025-03", "meses": 4, "zona": "Viru",
    "rubros": ["agro", "transporte"], "caida": 0.35,
    "prob_deterioro_posterior": 0.12,
}

NOMBRES = ["Rosa", "Pedro", "Luis", "Carmen", "Jorge", "Ana", "Miguel", "Lucia",
           "Juan", "Maria", "Carlos", "Elena", "Victor", "Gladys", "Raul", "Teresa",
           "Hugo", "Norma", "Cesar", "Flor", "Walter", "Silvia", "Javier", "Rocio"]

TASA_MENSUAL = 0.03          # tasa de interes mensual referencial
PROB_CUENTA_AHORRO = 0.65    # clientes con cuenta de ahorros activa
DESFASE_RCC_DIAS = 45        # dias hasta que la deuda del mes es conocida


def cuota_fija(monto, n, r=TASA_MENSUAL):
    return round(monto * r / (1 - (1 + r) ** -n), 2)


# ---------------------------------------------------------------------------
# Trayectoria de "salud" del negocio (1 = normal)
# ---------------------------------------------------------------------------

def trayectoria_salud(perfil, n_meses, rng):
    h = np.ones(n_meses)
    info = {"inicio_deterioro": None, "recupera": None, "mes_anomalia": None}
    if perfil == "deterioro":
        inicio = int(rng.integers(8, n_meses - 6))
        dur = int(rng.integers(4, 9))
        recupera = rng.random() < 0.30          # casos dificiles: senales sin mora
        piso = rng.uniform(0.72, 0.80) if recupera else rng.uniform(0.25, 0.45)
        for t in range(inicio, n_meses):
            k = t - inicio
            if k < dur:
                h[t] = 1 - (1 - piso) * (k + 1) / dur
            elif recupera:
                h[t] = min(1.0, piso + (1 - piso) * (k - dur + 1) / 3)
            else:
                h[t] = piso
        info.update(inicio_deterioro=inicio, recupera=recupera)
    elif perfil == "anomalia":
        m = int(rng.integers(6, n_meses - 2))
        h[m] = rng.uniform(0.68, 0.78)
        info["mes_anomalia"] = m
    return h, info


# ---------------------------------------------------------------------------
# Simulacion
# ---------------------------------------------------------------------------

def generar(n_clientes=5000, n_meses=36, inicio="2023-12", semilla=42):
    rng = np.random.default_rng(semilla)
    periodos = pd.period_range(inicio, periods=n_meses, freq="M")
    fen_ini = periodos.get_loc(pd.Period(FEN["inicio"], "M")) if pd.Period(FEN["inicio"], "M") in periodos else None

    clientes, creditos, pagos, ahorros, rcc, eventos = [], [], [], [], [], []
    id_credito = 0

    for i in range(n_clientes):
        cid = f"CLI-{i + 1:05d}"
        zona = rng.choice(ZONAS, p=PROB_ZONA)
        rubro = rng.choice(RUBROS, p=MEZCLA_RUBRO[zona])
        perfil = rng.choice(PERFILES, p=PROB_PERFIL)
        ventas = VENTAS_BASE[rubro] * rng.lognormal(0, 0.35)
        tiene_cuenta = rng.random() < PROB_CUENTA_AHORRO
        amp = 2.0 if perfil == "estacional" else 1.0   # amplitud estacional
        base_anticipacion = rng.uniform(4, 15)         # dias antes del vencimiento
        dia_venc = int(rng.integers(1, 29))

        h, info = trayectoria_salud(perfil, n_meses, rng)

        # Efecto El Nino sobre agro y transporte de la zona afectada
        afectado_fen = (fen_ini is not None and zona == FEN["zona"] and rubro in FEN["rubros"])
        fen_mult = np.ones(n_meses)      # efecto en ventas
        fen_pago = np.ones(n_meses)      # efecto en capacidad de pago (segun resiliencia)
        if afectado_fen:
            for k in range(FEN["meses"]):
                if fen_ini + k < n_meses:
                    fen_mult[fen_ini + k] = 1 - FEN["caida"] * (1 - k / (FEN["meses"] + 1))
            exposicion = rng.uniform(0.2, 0.9)
            fen_pago = 1 - (1 - fen_mult) * exposicion
            if perfil in ("estable", "estacional") and rng.random() < FEN["prob_deterioro_posterior"]:
                perfil = "deterioro_fen"
                piso = rng.uniform(0.40, 0.85)
                for t in range(fen_ini + FEN["meses"] - 1, n_meses):
                    h[t] = max(piso, 1 - 0.12 * (t - fen_ini - FEN["meses"] + 2))
                info["inicio_deterioro"] = fen_ini

        # Meses en que el cliente tiene credito activo
        if perfil == "nuevo":
            mes_alta = int(rng.integers(n_meses - 3, n_meses))
        else:
            mes_alta = 0
        antiguedad = int(rng.integers(6, 72)) if perfil != "nuevo" else 0

        clientes.append({
            "id_cliente": cid, "nombre_ficticio": rng.choice(NOMBRES), "rubro": rubro,
            "zona": zona, "perfil_simulado": perfil, "afectado_fen": afectado_fen,
            "tiene_cuenta_ahorro": tiene_cuenta, "antiguedad_meses": antiguedad,
            "ventas_base_mensual": round(ventas, 0),
            # Verdad de terreno: solo para evaluar el modelo, nunca como variable de entrada
            "eval_periodo_inicio_deterioro": str(periodos[info["inicio_deterioro"]]) if info["inicio_deterioro"] is not None else None,
        })

        # Creditos consecutivos (renovaciones) dentro de la ventana
        t = mes_alta
        monto = float(np.clip(round(ventas * rng.uniform(0.6, 2.5), -2), 2000, 40000))
        atraso = 0
        deuda_pendiente = 0.0
        primer_evento = None
        saldo_ahorro = ventas * rng.uniform(0.3, 1.2) if tiene_cuenta else np.nan

        # Deuda en otras entidades (tipo RCC)
        deuda_ext = rng.uniform(1000, 15000) if rng.random() < 0.40 else 0.0
        n_ent = int(rng.integers(1, 3)) if deuda_ext > 0 else 0
        mes_deuda_nueva = None
        if info["inicio_deterioro"] is not None and not info.get("recupera"):
            mes_deuda_nueva = info["inicio_deterioro"] + int(rng.integers(1, 4))
        elif rng.random() < 0.05:
            mes_deuda_nueva = int(rng.integers(0, n_meses))   # ruido: deuda nueva sin deterioro

        # Primer credito puede haber empezado antes de la ventana
        plazo = int(rng.choice([12, 18, 24]))
        cuotas_previas = int(rng.integers(0, plazo)) if perfil != "nuevo" else 0
        while t < n_meses:
            id_credito += 1
            crid = f"CR-{id_credito:06d}"
            cuota = cuota_fija(monto, plazo)
            desembolso = (periodos[t] - cuotas_previas).to_timestamp() + pd.Timedelta(days=int(rng.integers(0, 28)))
            creditos.append({
                "id_credito": crid, "id_cliente": cid, "monto": monto, "plazo_meses": plazo,
                "cuota": cuota, "dia_vencimiento": dia_venc, "fecha_desembolso": desembolso.date(),
            })
            restantes = plazo - cuotas_previas
            for _ in range(restantes):
                if t >= n_meses:
                    break
                p = periodos[t]
                mes_cal = p.month
                est = 1 + (ESTACIONALIDAD[rubro][mes_cal - 1] - 1) * amp
                ruido = rng.lognormal(0, 0.04)
                capacidad = h[t] * fen_pago[t] * ruido               # capacidad de pago
                actividad = h[t] * est * fen_mult[t] * ruido         # nivel de ventas del mes
                retraso_est = int(max(0.0, 0.92 - est) * 40)        # temporada baja: paga mas tarde

                # --- Pago de la cuota del mes
                venc = pd.Timestamp(p.year, p.month, dia_venc)
                if capacidad >= 0.85 and deuda_pendiente == 0:
                    frac = 1.0
                    dias = -int(round(base_anticipacion * min(1.0, (capacidad - 0.55) / 0.45))) + int(rng.integers(-1, 2)) + retraso_est
                elif capacidad >= 0.70 and deuda_pendiente == 0:
                    frac = 1.0
                    dias = int(rng.integers(-2, 9)) + retraso_est   # paga justo o algo tarde
                else:
                    frac = float(np.clip(capacidad / 0.75, 0.2, 1.0))
                    dias = int(rng.integers(3, 20)) if frac >= 1.0 else int(rng.integers(0, 15))
                pagado = round(cuota * frac, 2)
                # Recuperacion: abona parte de lo atrasado
                if capacidad >= 0.95 and deuda_pendiente > 0:
                    abono = min(deuda_pendiente, cuota * 0.6)
                    pagado = round(cuota + abono, 2)
                    deuda_pendiente -= abono
                    dias = int(rng.integers(0, 10))
                else:
                    deuda_pendiente += cuota - pagado

                # Dias de atraso del cliente al cierre del mes
                if deuda_pendiente >= 0.5 * cuota:
                    atraso = atraso + 30 if atraso > 0 else int(rng.integers(8, 25))
                else:
                    atraso = max(0, dias) if dias is not None else 0
                if atraso > 30 and primer_evento is None:
                    primer_evento = p

                pagos.append({
                    "id_credito": crid, "id_cliente": cid, "periodo": str(p),
                    "fecha_vencimiento": venc.date(),
                    "fecha_pago": (venc + pd.Timedelta(days=dias)).date() if dias is not None and pagado > 0 else None,
                    "monto_cuota": cuota, "monto_pagado": pagado,
                    "pago_parcial": pagado < cuota - 0.01,
                    "dias_atraso_cierre": int(atraso),
                })

                # --- Ahorros
                if tiene_cuenta:
                    dep = ventas * actividad * rng.uniform(0.30, 0.45)
                    ret = dep * (1 + (1 - min(h[t], 1)) * 0.8 + rng.normal(0, 0.05))
                    saldo_ahorro = max(0.0, saldo_ahorro + dep - ret)
                    ahorros.append({
                        "id_cliente": cid, "periodo": str(p), "depositos": round(dep, 2),
                        "retiros": round(ret, 2), "saldo_fin_mes": round(saldo_ahorro, 2),
                    })

                # --- Deuda en otras entidades (conocida con desfase)
                if mes_deuda_nueva is not None and t == mes_deuda_nueva:
                    deuda_ext += rng.uniform(1000, 5000)
                    n_ent += 1
                elif deuda_ext > 0:
                    deuda_ext *= 0.97
                rcc.append({
                    "id_cliente": cid, "periodo": str(p),
                    "deuda_otras_entidades": round(deuda_ext, 2), "num_entidades": n_ent,
                    "fecha_disponible": (p.to_timestamp(how="end") + pd.Timedelta(days=DESFASE_RCC_DIAS)).date(),
                })
                t += 1
                if atraso > 120:     # credito en perdida: no se renueva
                    t = n_meses
            # Renovacion si el cliente termino al dia
            cuotas_previas = 0
            if atraso > 30:
                # sigue simulando atraso sin nuevo credito hasta el final
                break
            monto = float(np.clip(round(monto * rng.uniform(1.0, 1.2), -2), 2000, 40000))
            plazo = int(rng.choice([12, 18, 24]))

        eventos.append({
            "id_cliente": cid,
            "periodo_primer_atraso_30": str(primer_evento) if primer_evento is not None else None,
        })

    return {
        "clientes": pd.DataFrame(clientes),
        "creditos": pd.DataFrame(creditos),
        "pagos": pd.DataFrame(pagos),
        "ahorros_mensual": pd.DataFrame(ahorros),
        "rcc_mensual": pd.DataFrame(rcc),
        "eventos_deterioro": pd.DataFrame(eventos),
    }


def resumen(tablas):
    cl = tablas["clientes"].merge(tablas["eventos_deterioro"], on="id_cliente")
    cl["deterioro"] = cl["periodo_primer_atraso_30"].notna()
    print(f"Clientes: {len(cl):,}  Creditos: {len(tablas['creditos']):,}  Pagos: {len(tablas['pagos']):,}")
    print(f"Con cuenta de ahorros: {cl['tiene_cuenta_ahorro'].mean():.0%}")
    print(f"Clientes que superan 30 dias de atraso: {cl['deterioro'].mean():.1%}")
    print("\nPor perfil simulado:")
    print(cl.groupby("perfil_simulado")["deterioro"].agg(["count", "mean"]).round(3).to_string())
    print("\nAfectados por evento FEN:", int(cl["afectado_fen"].sum()))


def main():
    ap = argparse.ArgumentParser(description="Generador de datos sinteticos ANTICIPA")
    ap.add_argument("--clientes", type=int, default=5000)
    ap.add_argument("--meses", type=int, default=36)
    ap.add_argument("--inicio", default="2023-12")
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--salida", default="datos")
    a = ap.parse_args()

    tablas = generar(a.clientes, a.meses, a.inicio, a.semilla)
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    for nombre, df in tablas.items():
        df.to_csv(out / f"{nombre}.csv", index=False)
    resumen(tablas)
    print(f"\nArchivos CSV guardados en: {out.resolve()}")


if __name__ == "__main__":
    main()
