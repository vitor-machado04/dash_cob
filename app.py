from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


DEFAULT_FILE = "Base Cobrança EDP 1.xlsx"
BASE_SHEET = "Base EDP"

STATUS_ORDER = [
	"pre_fatura",
	"auditoria",
	"agendada",
	"a_vencer",
	"paga",
	"atrasada",
	"cancelada",
	"arquivada",
	"parcelada",
]

STATUS_CODE_MAP = {
	1: "pre_fatura",
	2: "auditoria",
	3: "agendada",
	4: "a_vencer",
	5: "paga",
	6: "atrasada",
	7: "cancelada",
	8: "arquivada",
	10: "parcelada",
}

STATUS_LABEL_PT = {
	"pre_fatura": "1. pre_fatura",
	"auditoria": "2. auditoria",
	"agendada": "3. agendada",
	"a_vencer": "4. a vencer",
	"paga": "5. paga",
	"atrasada": "6. atrasada",
	"cancelada": "7. cancelada",
	"arquivada": "8. arquivada",
	"parcelada": "10. parcelada",
	"outros": "N/A",
}

MONEY_COLUMNS = ["Valor da Cobrança (R$)", "Valor em Atraso (R$)", "Valor Pago (R$)"]
DATE_COLUMNS = ["Data Emissão", "Data Vencimento", "Data Pagamento", "Vencimento Lex"]


def normalize_status(raw: object) -> str:
	if pd.isna(raw):
		return "outros"

	if isinstance(raw, float) and raw.is_integer():
		raw = int(raw)

	if isinstance(raw, int):
		return STATUS_CODE_MAP.get(raw, "outros")

	text = str(raw).strip().lower().replace(" ", "_")
	if text in STATUS_ORDER:
		return text

	if text.replace(".", "", 1).isdigit():
		num = int(float(text))
		return STATUS_CODE_MAP.get(num, "outros")

	return "outros"


@st.cache_data(show_spinner=False)
def load_data(file_path: str) -> pd.DataFrame:
	df = pd.read_excel(file_path, sheet_name=BASE_SHEET, engine="openpyxl")

	df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

	for col in MONEY_COLUMNS:
		if col in df.columns:
			df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

	for col in DATE_COLUMNS:
		if col in df.columns:
			df[col] = pd.to_datetime(df[col], errors="coerce")

	if "Mês de Referência" in df.columns:
		df["Mês de Referência"] = pd.to_numeric(df["Mês de Referência"], errors="coerce")

	if "status" in df.columns:
		df["status_norm"] = df["status"].apply(normalize_status)
	else:
		df["status_norm"] = "outros"

	df["status_label"] = df["status_norm"].map(STATUS_LABEL_PT).fillna("N/A")
	return df


def format_brl(value: float) -> str:
	if pd.isna(value):
		return "R$ 0,00"
	br = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
	return f"R$ {br}"


def status_order_labels() -> list[str]:
	labels = [STATUS_LABEL_PT[k] for k in STATUS_ORDER]
	labels.append("N/A")
	return labels


def resolve_excel_path(app_dir: Path) -> Path | None:
	preferred = app_dir / DEFAULT_FILE
	if preferred.exists():
		return preferred

	candidates = sorted(app_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
	if not candidates:
		return None

	return candidates[0]


def disparo_columns(df: pd.DataFrame) -> list[str]:
	return [
		c
		for c in df.columns
		if isinstance(c, str) and (c.startswith("AVISO_") or c.startswith("FATURA_"))
	]


def render_disparos_dashboard(df: pd.DataFrame) -> None:
	st.subheader("Disparos")

	cols = disparo_columns(df)
	if not cols:
		st.info(
			"Nao encontrei colunas de disparo (AVISO_* / FATURA_*) na aba Base EDP deste arquivo. "
			"Se esses campos estiverem em outra aba/fonte, me passe que eu integro no dashboard."
		)
		return

	base = df.copy()
	for col in cols:
		base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0)

	totals = (
		base[cols]
		.sum()
		.reset_index()
		.rename(columns={"index": "tipo_disparo", 0: "qtd_disparos"})
		.sort_values("qtd_disparos", ascending=False)
	)

	fig_total = px.bar(
		totals,
		x="tipo_disparo",
		y="qtd_disparos",
		text_auto=True,
		title="Quantidade total de disparos por tipo",
	)
	fig_total.update_layout(xaxis_title="Tipo de disparo", yaxis_title="Quantidade")
	st.plotly_chart(fig_total, use_container_width=True)

	aging_col = "Aging Alexandria" if "Aging Alexandria" in base.columns else "Aging edp"
	if aging_col in base.columns:
		by_aging = base[[aging_col, *cols]].copy()
		by_aging[aging_col] = by_aging[aging_col].fillna("Nao informado")
		aging_group = by_aging.groupby(aging_col, dropna=False)[cols].sum().reset_index()
		aging_long = aging_group.melt(
			id_vars=[aging_col],
			value_vars=cols,
			var_name="tipo_disparo",
			value_name="qtd_disparos",
		)

		fig_aging = px.bar(
			aging_long,
			x=aging_col,
			y="qtd_disparos",
			color="tipo_disparo",
			title="Disparos por aging e tipo",
		)
		fig_aging.update_layout(xaxis_title="Aging", yaxis_title="Quantidade")
		st.plotly_chart(fig_aging, use_container_width=True)

		st.markdown("Tabela de disparos por aging")
		st.dataframe(aging_group, use_container_width=True, hide_index=True)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
	st.sidebar.header("Filtros")

	selected_status = st.sidebar.multiselect(
		"Status",
		options=status_order_labels(),
		default=[],
		placeholder="Selecione para filtrar (vazio = todos)",
	)

	filtered = df[df["status_label"].isin(selected_status)] if selected_status else df

	if "Mês de Referência" in df.columns:
		months = sorted(df["Mês de Referência"].dropna().astype(int).unique().tolist())
		selected_months = st.sidebar.multiselect(
			"Mês de Referência",
			options=months,
			default=[],
			placeholder="Selecione para filtrar (vazio = todos)",
		)
		if selected_months:
			filtered = filtered[filtered["Mês de Referência"].astype("Int64").isin(selected_months)]

	search_client = st.sidebar.text_input("Buscar cliente (Razão Social / Nome)")
	if search_client and "Razão Social / Nome" in filtered.columns:
		filtered = filtered[
			filtered["Razão Social / Nome"].astype(str).str.contains(search_client, case=False, na=False)
		]

	return filtered


def render_kpis(df: pd.DataFrame) -> None:
	total_envios = len(df)
	total_atraso = df["Valor em Atraso (R$)"].sum() if "Valor em Atraso (R$)" in df.columns else 0.0
	total_faturas = df["Invoice Num"].nunique() if "Invoice Num" in df.columns else 0

	c1, c2, c3 = st.columns(3)
	c1.metric("Envios de cobrança", f"{total_envios:,}".replace(",", "."))
	c2.metric("Faturas únicas", f"{total_faturas:,}".replace(",", "."))
	c3.metric("Total em atraso", format_brl(total_atraso))


def render_status_dashboards(df: pd.DataFrame) -> None:
	st.subheader("Status das cobranças")

	status_group_raw = (
		df.groupby("status_label", dropna=False)
		.agg(
			quantidade=("ID Cobranca", "count") if "ID Cobranca" in df.columns else ("status_label", "count"),
			valor_em_atraso=("Valor em Atraso (R$)", "sum") if "Valor em Atraso (R$)" in df.columns else ("status_label", "count"),
		)
		.reset_index()
	)

	all_status = pd.DataFrame({"status_label": status_order_labels()})
	status_group = all_status.merge(status_group_raw, on="status_label", how="left").fillna(0)

	c1, c2 = st.columns(2)

	fig_qtd = px.bar(
		status_group,
		x="status_label",
		y="quantidade",
		text_auto=True,
		title="Quantidade por status",
	)
	fig_qtd.update_layout(xaxis_title="Status", yaxis_title="Quantidade", showlegend=False)
	c1.plotly_chart(fig_qtd, use_container_width=True)

	fig_valor = px.bar(
		status_group,
		x="status_label",
		y="valor_em_atraso",
		text_auto=".2s",
		title="Valor por status",
	)
	fig_valor.update_layout(xaxis_title="Status", yaxis_title="Valor em atraso (R$)", showlegend=False)
	c2.plotly_chart(fig_valor, use_container_width=True)


def render_time_and_aging(df: pd.DataFrame) -> None:
	st.subheader("Tempo e aging")

	c1, c2 = st.columns(2)

	if "Mês de Referência" in df.columns and "Valor em Atraso (R$)" in df.columns:
		month_df = (
			df.dropna(subset=["Mês de Referência"])
			.groupby("Mês de Referência", as_index=False)
			.agg(valor_em_atraso=("Valor em Atraso (R$)", "sum"))
			.sort_values("Mês de Referência")
		)
		month_df["Mês de Referência"] = month_df["Mês de Referência"].astype("Int64").astype(str)

		fig_month = px.line(
			month_df,
			x="Mês de Referência",
			y="valor_em_atraso",
			markers=True,
			title="Evolução de valor em atraso por mês de referência",
		)
		fig_month.update_layout(yaxis_title="Valor em atraso (R$)")
		c1.plotly_chart(fig_month, use_container_width=True)

	aging_col = "Aging Alexandria" if "Aging Alexandria" in df.columns else "Aging edp"
	if aging_col in df.columns:
		aging_df = (
			df.groupby(aging_col, dropna=False)
			.agg(valor_em_atraso=("Valor em Atraso (R$)", "sum"), envios=("ID Cobranca", "count"))
			.reset_index()
			.rename(columns={aging_col: "aging"})
			.sort_values("valor_em_atraso", ascending=False)
		)
		aging_df["aging"] = aging_df["aging"].fillna("Não informado")

		fig_aging = px.bar(
			aging_df,
			x="aging",
			y="valor_em_atraso",
			text_auto=".2s",
			title=f"Valor por aging ({aging_col})",
		)
		fig_aging.update_layout(xaxis_title="Aging", yaxis_title="Valor em atraso (R$)")
		c2.plotly_chart(fig_aging, use_container_width=True)


def render_invoice_and_clients(df: pd.DataFrame) -> None:
	st.subheader("Ranking por cliente")
	if "Razão Social / Nome" in df.columns:
		client_rank = (
			df.groupby("Razão Social / Nome", dropna=False)
			.agg(
				envios=("ID Cobranca", "count") if "ID Cobranca" in df.columns else ("Razão Social / Nome", "count"),
				valor_em_atraso=("Valor em Atraso (R$)", "sum") if "Valor em Atraso (R$)" in df.columns else ("Razão Social / Nome", "count"),
			)
			.reset_index()
			.sort_values(["valor_em_atraso", "envios"], ascending=[False, False])
		)

		st.markdown("Ranking por cliente")
		top_clients = client_rank.head(20)
		fig_clients = px.bar(
			top_clients,
			x="valor_em_atraso",
			y="Razão Social / Nome",
			orientation="h",
			text_auto=".2s",
			title="Top 20 clientes por valor em atraso",
		)
		fig_clients.update_layout(xaxis_title="Valor em atraso (R$)", yaxis_title="Cliente")
		st.plotly_chart(fig_clients, use_container_width=True)

		table_clients = top_clients.copy()
		table_clients["valor_em_atraso"] = table_clients["valor_em_atraso"].map(format_brl)
		st.dataframe(table_clients, use_container_width=True, hide_index=True)
	else:
		st.info("A coluna Razão Social / Nome nao existe na base atual, entao o ranking por cliente nao pode ser montado.")


def main() -> None:
	st.set_page_config(page_title="Dashboard Cobrança EDP", page_icon="📊", layout="wide")
	st.caption("Visão analítica de envios de cobrança por fatura, status, aging e evolução temporal.")

	app_dir = Path(__file__).parent
	default_path = resolve_excel_path(app_dir)
	if default_path is None:
		st.error("Nenhum arquivo .xlsx encontrado na pasta do app.")
		st.stop()

	st.caption(f"Fonte de dados: {default_path.name}")

	try:
		df = load_data(file_path=str(default_path))
	except Exception as exc:
		st.exception(exc)
		st.stop()

	filtered_df = apply_filters(df)
	if filtered_df.empty:
		st.warning("Sem dados para os filtros selecionados.")
		st.stop()

	render_kpis(filtered_df)
	st.divider()
	render_status_dashboards(filtered_df)
	st.divider()
	render_time_and_aging(filtered_df)
	st.divider()
	render_disparos_dashboard(filtered_df)
	st.divider()
	render_invoice_and_clients(filtered_df)

	st.download_button(
		label="Baixar dados filtrados (CSV)",
		data=filtered_df.to_csv(index=False).encode("utf-8"),
		file_name="base_edp_filtrada.csv",
		mime="text/csv",
	)


if __name__ == "__main__":
	main()
