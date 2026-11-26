import numpy as np
import plotly.graph_objects as go
import streamlit as st

import store
import ui

ctx = store.load_state(store.current_state())
ex = ctx.explorer.copy()
ex["purpose"] = ex.purpose_label.map(store.PURPOSE)
ex["ltype"] = ex.loan_type.map(store.LOAN_TYPE)
ex["chan"] = ex.channel.map(store.CHANNEL).fillna("Other")

st.title("Funnel explorer")
st.write(f"Slice {ctx.name}'s {ctx.total:,} applications by purpose, loan type, channel, income and loan size. "
         "The flow, the comparison with the state average and the heat map all update.")

with st.container(border=True, key="card-filters"):
    c1, c2, c3 = st.columns(3)
    purposes = c1.pills("Loan purpose", list(store.PURPOSE.values()), selection_mode="multi", default=list(store.PURPOSE.values()))
    ltypes = c2.pills("Loan type", list(store.LOAN_TYPE.values()), selection_mode="multi", default=list(store.LOAN_TYPE.values()))
    chans = c3.pills("Channel", ["Direct", "Broker", "Other"], selection_mode="multi", default=["Direct", "Broker", "Other"],
                     help="Direct = applied straight to the lender. Broker = through a third party. Other = not applicable / exempt.")
    d1, d2 = st.columns(2)
    inc_lo, inc_hi = d1.select_slider("Income fifth (1 = lowest, 0 = not reported)", options=[0, 1, 2, 3, 4, 5], value=(0, 5))
    sz_lo, sz_hi = d2.select_slider("Loan size quartile within purpose (1 = smallest)", options=[1, 2, 3, 4], value=(1, 4))

base_mask = ex.purpose.isin(purposes) & ex.ltype.isin(ltypes) & ex.chan.isin(chans)
mask = base_mask & ex.inc_band.between(inc_lo, inc_hi) & ex.size_band.between(sz_lo, sz_hi)
sel = ex[mask]
if sel.empty or sel.apps.sum() == 0:
    st.warning("No applications match these filters. Widen the selection.")
    st.stop()

n = int(sel.apps.sum())
tot = {o: int(sel[store.SHORT[o]].sum()) for o in store.OUTCOMES}
base = {o: int(ex[store.SHORT[o]].sum()) for o in store.OUTCOMES}
ui.kpis([
    dict(label="Applications in view", value=n / 1000 if n >= 10000 else n, decimals=1 if n >= 10000 else 0, unit="K" if n >= 10000 else "",
         color="#6EA8FF", sub=f"{100 * n / ctx.total:.1f}% of {ctx.name}"),
    dict(label="Funded", value=100 * tot["originated"] / n, unit="%", color=store.TEAL, sub=f"state {100 * base['originated'] / ctx.total:.1f}%"),
    dict(label="Denied", value=100 * tot["lender_denied"] / n, unit="%", color=store.ROSE, sub=f"state {100 * base['lender_denied'] / ctx.total:.1f}%"),
    dict(label="Applicant walked away", value=100 * (tot["customer_withdrew"] + tot["stalled_incomplete"] + tot["customer_declined"]) / n,
         unit="%", color=store.ORANGE, sub=f"state {100 * ctx.walked / ctx.total:.1f}%"),
    dict(label="File closed incomplete", value=100 * tot["stalled_incomplete"] / n, unit="%", color=store.AMBER,
         sub=f"state {100 * base['stalled_incomplete'] / ctx.total:.1f}%"),
])

# ---------------------------------------------------------------- sankey
st.subheader("Where the selected applications end up")
seg = sel.groupby(["purpose", "chan"])[["apps"] + [store.SHORT[o] for o in store.OUTCOMES]].sum().reset_index()
seg = seg[seg.apps > 0]
seg["name"] = seg.purpose + " · " + seg.chan
labels = [f"All applications ({n:,})"] + [f"{r['name']} ({int(r.apps):,})" for _, r in seg.iterrows()] + \
         [f"{store.OUTCOME_LABEL[o]} ({tot[o]:,})" for o in store.OUTCOMES]
src, dst, val, col = [], [], [], []
for i, (_, r) in enumerate(seg.iterrows()):
    src.append(0); dst.append(1 + i); val.append(int(r.apps)); col.append("rgba(143,160,194,.28)")
    for j, o in enumerate(store.OUTCOMES):
        v = int(r[store.SHORT[o]])
        if v:
            h = store.COLOR[o].lstrip("#")
            src.append(1 + i); dst.append(1 + len(seg) + j); val.append(v)
            col.append(f"rgba({int(h[:2], 16)},{int(h[2:4], 16)},{int(h[4:], 16)},.42)")
node_colors = ["#8FA0C2"] + ["#6EA8FF"] * len(seg) + [store.COLOR[o] for o in store.OUTCOMES]
fig = go.Figure(go.Sankey(
    arrangement="snap", textfont=dict(color="#E8ECF5", size=13, family="Inter"),
    node=dict(pad=16, thickness=16, label=labels, color=node_colors, line=dict(width=0),
              hovertemplate="%{label}<br>%{value:,} applications<extra></extra>"),
    link=dict(source=src, target=dst, value=val, color=col, hovertemplate="%{source.label} → %{target.label}<br>%{value:,}<extra></extra>")))
st.plotly_chart(ui.style(fig, 430, legend=False, margin=dict(l=4, r=4, t=10, b=4)), width="stretch", config={"displayModeBar": False},
                key="fun_sankey", alt="Sankey diagram of selected applications flowing from purpose and channel segments to outcomes")

# ---------------------------------------------------------------- selection vs state
left, right = st.columns([1, 1.1])
with left:
    st.subheader("Selection vs state average")
    fig = go.Figure()
    fig.add_bar(y=[store.OUTCOME_LABEL[o] for o in store.OUTCOMES], x=[100 * base[o] / ctx.total for o in store.OUTCOMES], orientation="h",
                name=f"All of {ctx.state}", marker_color="rgba(143,160,194,.45)")
    fig.add_bar(y=[store.OUTCOME_LABEL[o] for o in store.OUTCOMES], x=[100 * tot[o] / n for o in store.OUTCOMES], orientation="h",
                name="Selection", marker_color=[store.COLOR[o] for o in store.OUTCOMES],
                text=[f"{100 * tot[o] / n:.1f}%" for o in store.OUTCOMES], textposition="outside", textfont=dict(color="#E8ECF5"))
    fig.update_layout(barmode="group", bargap=0.35)
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(ticksuffix="%", title=None, range=[0, 78])
    st.plotly_chart(ui.style(fig, 340), width="stretch", config={"displayModeBar": False}, key="fun_cmp",
                    alt="Outcome shares for the selection compared with the state average")

with right:
    st.subheader("Heat map: income × loan size")
    metric = st.segmented_control("Show", ["Walk-away", "Funded", "Denied", "Closed incomplete"], default="Walk-away", required=True, key="fun_metric")
    hm = ex[base_mask & (ex.inc_band >= 1) & (ex.size_band >= 1)].groupby(["inc_band", "size_band"])[["apps"] + [store.SHORT[o] for o in store.OUTCOMES]].sum()
    num = {"Walk-away": hm.withdrew + hm.incomplete + hm.declined, "Funded": hm.originated, "Denied": hm.denied, "Closed incomplete": hm.incomplete}[metric]
    z = (100 * num / hm.apps).where(hm.apps >= 100).unstack()
    cells = hm.apps.unstack()
    scale = {"Walk-away": "Oranges", "Funded": "Teal", "Denied": "Reds", "Closed incomplete": "YlOrBr"}[metric]
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[f"Q{c}" for c in z.columns], y=[f"Income {r}/5" for r in z.index], colorscale=scale, zmin=0,
        text=np.where(np.isnan(z.values), "", np.round(z.values, 1).astype(str)), texttemplate="%{text}%", textfont=dict(size=12, color="#0B1020"),
        customdata=cells.reindex(index=z.index, columns=z.columns).values, colorbar=dict(ticksuffix="%", thickness=10, len=0.9),
        hovertemplate="%{y}, loan size %{x}<br>" + metric + ": %{z:.1f}%<br>%{customdata:,} applications<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Loan size quartile within purpose", side="bottom")
    st.plotly_chart(ui.style(fig, 340, legend=False), width="stretch", config={"displayModeBar": False}, key="fun_heat",
                    alt="Heat map of the chosen outcome rate by income fifth and loan size quartile")
    st.caption("Uses the purpose / loan type / channel filters only. Cells with fewer than 100 applications are blank.")

# ---------------------------------------------------------------- direct vs broker by loan type
st.subheader("Direct vs broker, by loan type")
seg2 = ctx.segments.copy()
seg2["ltype"] = seg2.loan_type.map(store.LOAN_TYPE)
seg2 = seg2[seg2.channel_label.isin(["direct", "indirect"])]
fig = go.Figure()
for ch, color in [("direct", store.ORANGE), ("indirect", store.TEAL)]:
    d = seg2[seg2.channel_label == ch]
    fig.add_bar(x=d.ltype, y=d.walkaway_pct, name=store.CHANNEL[ch], marker_color=color, text=[f"{v:.0f}%" for v in d.walkaway_pct],
                textposition="outside", customdata=d.apps, hovertemplate="%{x} · " + store.CHANNEL[ch] + "<br>walk-away %{y:.1f}% of %{customdata:,}<extra></extra>")
fig.add_hline(y=100 * ctx.walked / ctx.total, line=dict(color="#8FA0C2", dash="dot"),
              annotation_text=f"{ctx.state} average", annotation_font_color="#8FA0C2")
fig.update_layout(barmode="group", bargap=0.3)
fig.update_yaxes(ticksuffix="%", title="Walk-away rate")
st.plotly_chart(ui.style(fig, 320), width="stretch", config={"displayModeBar": False}, key="fun_chan",
                alt="Walk-away rate by loan type for direct and broker channels")
st.caption("Loan type × channel segments with 500+ applications. Direct applicants leave more often than broker applicants for every loan type shown; "
           "brokers pre-screen and coach applicants, so not all of the gap is recoverable.")
