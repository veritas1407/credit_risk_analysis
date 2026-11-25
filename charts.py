"""
charts.py: Plotly figures used on more than one page. Page-specific charts live in the page files.
"""

import numpy as np
import plotly.graph_objects as go

import store
import ui


def segment_bars(ctx, height: int = 330):
    """Share of applications by outcome for each purpose x channel segment (100% stacked)."""
    lk = ctx.leak.copy()
    lk["segment"] = lk.purpose_label.map(store.PURPOSE) + " · " + lk.channel_label.map(store.CHANNEL)
    lk = lk[lk.apps >= 300].sort_values("apps")
    fig = go.Figure()
    for o in store.OUTCOMES:
        share = lk[store.SHORT[o]] / lk.apps
        fig.add_bar(
            y=lk.segment, x=share * 100, orientation="h", name=store.OUTCOME_LABEL[o], marker_color=store.COLOR[o],
            text=[f"{100 * v:.0f}%" if v >= 0.045 else "" for v in share], textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#0B1020", size=12, family="Inter"),
            customdata=np.c_[lk[store.SHORT[o]], lk.apps],
            hovertemplate="<b>%{y}</b><br>" + store.OUTCOME_LABEL[o] + ": %{x:.1f}% (%{customdata[0]:,} of %{customdata[1]:,})<extra></extra>",
        )
    fig.update_layout(barmode="stack", bargap=0.28)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title=None)
    fig.update_yaxes(title=None)
    return ui.style(fig, height)


def dumbbell(states_df, selected: str, height: int = 330):
    """Direct vs broker refinance 'closed incomplete' rate, one row per state."""
    d = states_df.copy()
    d["name"] = d.state.map(store.STATES)
    d = d.sort_values("dir_refi_inc_pct")
    fig = go.Figure()
    for _, r in d.iterrows():
        fig.add_shape(type="line", x0=r.ind_refi_inc_pct, x1=r.dir_refi_inc_pct, y0=r["name"], y1=r["name"],
                      line=dict(color="rgba(255,255,255,.28)" if r.state != selected else "#E8ECF5", width=3 if r.state == selected else 2))
    fig.add_trace(go.Scatter(
        x=d.dir_purch_inc_pct, y=d["name"], mode="markers", name="Direct purchase", marker=dict(color=store.GREY, size=9, symbol="diamond"),
        hovertemplate="%{y}<br>Direct purchase: %{x:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=d.ind_refi_inc_pct, y=d["name"], mode="markers", name="Broker refinance", marker=dict(color=store.TEAL, size=13),
        customdata=d.ind_refi_apps, hovertemplate="%{y}<br>Broker refinance: %{x:.1f}% (%{customdata:,} applications)<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=d.dir_refi_inc_pct, y=d["name"], mode="markers+text", name="Direct refinance", text=[f"{v:.1f}%" for v in d.dir_refi_inc_pct],
        textposition="middle right", textfont=dict(color=store.ORANGE, size=12), marker=dict(color=store.ORANGE, size=15),
        customdata=d.dir_refi_apps, hovertemplate="%{y}<br>Direct refinance: %{x:.1f}% (%{customdata:,} applications)<extra></extra>"))
    fig.update_xaxes(ticksuffix="%", range=[0, max(14, d.dir_refi_inc_pct.max() * 1.18)], title="Files closed as incomplete")
    fig.update_yaxes(title=None)
    return ui.style(fig, height)
