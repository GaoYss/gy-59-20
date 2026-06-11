from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Appointment, Rule

rules_bp = Blueprint("rules", __name__, url_prefix="/api/rules")


def calc_weekend_impact(rule_id, new_allow_weekend=None, current_allow_weekend=None):
    rule = Rule.query.get(rule_id)
    if not rule:
        return None
    result = {
        "totalActiveAppointments": 0,
        "weekendAppointments": 0,
        "affectedAppointments": 0,
        "affectedDetails": [],
    }
    active = Appointment.query.filter(
        Appointment.subject == rule.subject,
        Appointment.status.in_(["已预约", "已确认"]),
    ).all()
    result["totalActiveAppointments"] = len(active)
    for apt in active:
        if apt.exam_date.weekday() >= 5:
            result["weekendAppointments"] += 1

    actual_current = (
        current_allow_weekend
        if current_allow_weekend is not None
        else rule.allow_weekend
    )
    if (actual_current and new_allow_weekend is False) or (
        actual_current and new_allow_weekend is None
    ):
        for apt in active:
            if apt.exam_date.weekday() >= 5:
                result["affectedAppointments"] += 1
                result["affectedDetails"].append(
                    {
                        "id": apt.id,
                        "studentName": apt.student_name,
                        "idNumber": apt.id_number,
                        "examDate": apt.exam_date.isoformat(),
                        "timeslot": apt.timeslot,
                        "status": apt.status,
                    }
                )
    return result


@rules_bp.get("")
def list_rules():
    rules = Rule.query.order_by(Rule.id.asc()).all()
    return jsonify([rule.to_dict() for rule in rules])


@rules_bp.get("/<int:rule_id>/impact-preview")
def rule_impact_preview(rule_id):
    allow_weekend = request.args.get("allowWeekend")
    new_allow_weekend = None
    if allow_weekend is not None:
        new_allow_weekend = allow_weekend.lower() in ("true", "1", "yes")
    impact = calc_weekend_impact(rule_id, new_allow_weekend)
    if impact is None:
        return jsonify({"message": "规则不存在"}), 404
    return jsonify(impact)


@rules_bp.patch("/<int:rule_id>")
def update_rule(rule_id):
    rule = Rule.query.get_or_404(rule_id)
    payload = request.get_json() or {}

    previous_allow_weekend = rule.allow_weekend

    int_fields = {
        "minIntervalDays": "min_interval_days",
        "maxDailySlots": "max_daily_slots",
        "passingScore": "passing_score",
        "makeupWaitDays": "makeup_wait_days",
    }
    for api_key, model_key in int_fields.items():
        if api_key in payload:
            value = int(payload[api_key])
            if value < 0:
                return jsonify({"message": f"{api_key} 不能小于 0"}), 400
            setattr(rule, model_key, value)

    if "allowWeekend" in payload:
        rule.allow_weekend = bool(payload["allowWeekend"])
    if "enabled" in payload:
        rule.enabled = bool(payload["enabled"])

    db.session.commit()

    response_data = rule.to_dict()

    if previous_allow_weekend and not rule.allow_weekend:
        impact = calc_weekend_impact(
            rule_id, new_allow_weekend=False, current_allow_weekend=True
        )
        response_data["weekendImpact"] = {
            "message": (
                f"已从「允许周末」变更为「禁止周末」，当前有 {impact['affectedAppointments']} 个"
                f"周末预约（共 {impact['totalActiveAppointments']} 个有效预约）不受影响，"
                f"均为规则变更前创建。"
            ),
            "affectedCount": impact["affectedAppointments"],
            "totalActiveCount": impact["totalActiveAppointments"],
            "affectedDetails": impact["affectedDetails"],
        }

    return jsonify(response_data)
