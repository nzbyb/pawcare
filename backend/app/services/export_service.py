"""经营报表导出。

只导出运营统计与同期订单明细，不导出任何账号凭据、支付密钥或
请求日志；工作簿在内存里生成，不落盘。
"""

from datetime import date, timedelta
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.boarding import BoardingOrder, Kennel
from app.models.pet import Pet
from app.services import admin_service

HEADER_FILL = PatternFill("solid", fgColor="2F6B4F")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14)
MONEY = "#,##0.00"


def _write_header(sheet, headers: list[str]) -> None:
    sheet.append(headers)
    for index, _ in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=index)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"


def _autosize(sheet) -> None:
    for column in range(1, sheet.max_column + 1):
        width = max(
            len(str(sheet.cell(row=row, column=column).value or ""))
            for row in range(1, sheet.max_row + 1)
        )
        sheet.column_dimensions[get_column_letter(column)].width = min(
            42, max(10, width * 1.6)
        )


def statistics_workbook(db: Session, days: int) -> tuple[str, bytes]:
    """返回 (文件名, xlsx 字节)。days 只允许 7 / 30，与后台看板一致。"""
    stats = admin_service.statistics(db, days)
    start = date.fromisoformat(str(stats["start_date"]))
    end = date.fromisoformat(str(stats["end_date"]))

    book = Workbook()
    overview = book.active
    overview.title = "汇总"
    overview["A1"] = f"PawCare 经营汇总（{start} 至 {end}）"
    overview["A1"].font = TITLE_FONT
    rows = [
        ("统计区间", f"{start} 至 {end}"),
        ("新增订单", stats["orders"]),
        ("实收金额", stats["received"]),
        ("退款金额", stats["refunded"]),
        ("净收款", stats["net"]),
        ("今日实际入住率", f"{stats['occupancy_rate']}%"),
        ("在住笼舍 / 笼舍总数", f"{stats['actual_occupied']} / {stats['kennel_total']}"),
    ]
    for offset, (label, value) in enumerate(rows, start=3):
        overview.cell(row=offset, column=1, value=label).font = Font(bold=True)
        cell = overview.cell(row=offset, column=2, value=value)
        if label in ("实收金额", "退款金额", "净收款"):
            cell.number_format = MONEY
    overview.column_dimensions["A"].width = 22
    overview.column_dimensions["B"].width = 28

    daily = book.create_sheet("每日明细")
    _write_header(daily, ["日期", "新增订单", "实收", "退款", "净收款"])
    for row in stats["daily"]:
        daily.append([row["date"], row["orders"], row["received"], row["refunded"], row["net"]])
    for row in daily.iter_rows(min_row=2):
        for cell in row[2:]:
            cell.number_format = MONEY
    _autosize(daily)

    # 同期订单：只列业务字段，不含备注里的联系方式等自由文本以外的个人信息。
    orders = (
        db.query(BoardingOrder, Pet.name, Kennel.code)
        .join(Pet, BoardingOrder.pet_id == Pet.id)
        .join(Kennel, BoardingOrder.kennel_id == Kennel.id)
        .filter(
            BoardingOrder.create_time >= start,
            BoardingOrder.create_time < end + timedelta(days=1),
        )
        .order_by(BoardingOrder.id.desc())
        .all()
    )
    detail = book.create_sheet("同期订单")
    _write_header(
        detail,
        ["订单号", "宠物", "笼舍", "入住", "退房", "晚数", "状态", "总额", "已付", "支付状态"],
    )
    for order, pet_name, kennel_code in orders:
        detail.append(
            [
                order.id,
                pet_name,
                kennel_code,
                str(order.start_date),
                str(order.end_date),
                (order.end_date - order.start_date).days,
                order.status,
                float(order.total_amount),
                float(order.paid_amount or 0),
                order.payment_status,
            ]
        )
    for row in detail.iter_rows(min_row=2):
        row[7].number_format = MONEY
        row[8].number_format = MONEY
    _autosize(detail)

    buffer = BytesIO()
    book.save(buffer)
    filename = f"pawcare-statistics-{date.today().isoformat()}-{days}d.xlsx"
    return filename, buffer.getvalue()
