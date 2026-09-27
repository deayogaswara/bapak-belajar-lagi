import ast
from decimal import Decimal, DivisionByZero, InvalidOperation


_TOOL_CALL_LOG: list[dict[str, str]] = []


class CalculatorError(ValueError):
    """Raised when an arithmetic expression is unsafe or unsupported."""


def _format_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise CalculatorError("Hasil perhitungan tidak valid.")

    normalized = value.normalize()

    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))

    # Hindari scientific notation untuk hasil normal.
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _eval_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value, (int, float)
        ):
            raise CalculatorError("Hanya angka yang didukung.")
        return Decimal(str(node.value))

    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand)

        if isinstance(node.op, ast.UAdd):
            return value

        if isinstance(node.op, ast.USub):
            return -value

        raise CalculatorError("Operator unary tidak didukung.")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        try:
            if isinstance(node.op, ast.Add):
                return left + right

            if isinstance(node.op, ast.Sub):
                return left - right

            if isinstance(node.op, ast.Mult):
                return left * right

            if isinstance(node.op, ast.Div):
                return left / right

            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise CalculatorError("Tidak bisa membagi dengan nol.")
                return Decimal(left // right)

            if isinstance(node.op, ast.Mod):
                return left % right

            if isinstance(node.op, ast.Pow):
                # Batasi pangkat untuk mencegah perhitungan ekstrem.
                if right != right.to_integral():
                    raise CalculatorError(
                        "Pangkat desimal belum didukung."
                    )

                exponent = int(right)

                if abs(exponent) > 20:
                    raise CalculatorError(
                        "Nilai pangkat terlalu besar."
                    )

                return left ** exponent

        except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
            raise CalculatorError(
                "Perhitungan tidak valid atau membagi dengan nol."
            ) from exc

        raise CalculatorError("Operator tidak didukung.")

    raise CalculatorError(
        "Ekspresi mengandung sintaks yang tidak diizinkan."
    )


def calculate(expression: str) -> dict[str, str]:
    """
    Menghitung ekspresi aritmetika numerik secara aman.

    Gunakan tool ini setiap kali pertanyaan membutuhkan perhitungan
    dengan angka eksplisit, misalnya kecepatan, luas, persentase,
    pecahan desimal, penjumlahan, pengurangan, perkalian, pembagian,
    atau pangkat.

    Jangan gunakan tool ini untuk pertanyaan konseptual murni atau
    manipulasi aljabar simbolik.

    Operator yang didukung: +, -, *, /, //, %, **, dan tanda kurung.

    Args:
        expression: Ekspresi aritmetika numerik, contoh "150 / 2.5".

    Returns:
        Dictionary berisi ekspresi dan hasil perhitungan.
    """
    expression = expression.strip().replace("^", "**")

    if not expression:
        raise CalculatorError("Ekspresi tidak boleh kosong.")

    if len(expression) > 200:
        raise CalculatorError("Ekspresi terlalu panjang.")

    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_node(parsed)
        formatted = _format_decimal(result)

    except SyntaxError as exc:
        raise CalculatorError(
            "Format ekspresi tidak valid."
        ) from exc

    output = {
        "expression": expression,
        "result": formatted,
    }

    _TOOL_CALL_LOG.append(output.copy())
    return output


def clear_tool_call_log():
    _TOOL_CALL_LOG.clear()


def get_tool_call_log() -> list[dict[str, str]]:
    return [item.copy() for item in _TOOL_CALL_LOG]
