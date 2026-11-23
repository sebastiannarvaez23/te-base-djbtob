"""
tests/unit/validators/test_validators.py
────────────────────────────────────────
Tests unitarios para wa.validators (Field, RequestBody, ValidationError,
ValidationCode).

Sin base de datos — el módulo no interactúa con el ORM.
Sin marcadores de pytest — compatible con el runner de Django.
"""

import unittest

from core.validators import Field, RequestBody, ValidationCode, ValidationError
from necore.query.patterns import PATTERN_TEXT


# ── Helpers de test ───────────────────────────────────────────────────────────

def _make_field(field_type=None, **kwargs) -> Field:
    """
    Crea un Field con el atributo `name` asignado manualmente.
    Simula lo que Python hace con __set_name__ al definir una clase.
    """
    if field_type is str:
        kwargs.setdefault('max_length', 255)
        if not (
            kwargs.get('is_uuid')
            or kwargs.get('is_email')
            or kwargs.get('choices') is not None
            or kwargs.get('pattern') is not None
        ):
            kwargs['pattern'] = PATTERN_TEXT
    f = Field(field_type, **kwargs)
    f.name = "campo"
    return f


def _codes(errors: list) -> list:
    """Extrae la lista de ValidationCode de un conjunto de ValidationError."""
    return [e.code for e in errors]


def _fields_with_error(errors: list) -> list:
    """Extrae los nombres de campo de un conjunto de ValidationError."""
    return [e.field for e in errors]


# ══════════════════════════════════════════════════════════════════════════════
# ValidationError
# ══════════════════════════════════════════════════════════════════════════════

class TestValidationError(unittest.TestCase):
    """Verifica la correcta serialización de ValidationError."""

    def test_to_dict_contiene_todas_las_claves(self):
        error = ValidationError("email", ValidationCode.INVALID_EMAIL, "Correo inválido.")
        d = error.to_dict()
        self.assertIn("field",  d)
        self.assertIn("code",   d)
        self.assertIn("detail", d)

    def test_to_dict_code_es_string_no_enum(self):
        """El código debe serializarse como string (no como instancia de enum)."""
        error = ValidationError("email", ValidationCode.INVALID_EMAIL, "Correo inválido.")
        self.assertIsInstance(error.to_dict()["code"], str)
        self.assertEqual(error.to_dict()["code"], "INVALID_EMAIL")

    def test_to_dict_mapea_campo_y_detalle(self):
        error = ValidationError("nombre", ValidationCode.REQUIRED, "Es requerido.")
        d = error.to_dict()
        self.assertEqual(d["field"],  "nombre")
        self.assertEqual(d["detail"], "Es requerido.")

    def test_todos_los_codigos_tienen_valor_string(self):
        """Garantiza que ningún ValidationCode sea accidentalmente no-serializable."""
        for code in ValidationCode:
            error = ValidationError("x", code, "detalle")
            self.assertIsInstance(error.to_dict()["code"], str)


# ══════════════════════════════════════════════════════════════════════════════
# Field – validación de null
# ══════════════════════════════════════════════════════════════════════════════

class TestFieldNull(unittest.TestCase):
    """Casos de None/null con las banderas nullable y not-nullable."""

    def test_none_no_nullable_levanta_null_not_allowed(self):
        field = _make_field(str, nullable=False)
        self.assertIn(ValidationCode.NULL_NOT_ALLOWED, _codes(field.validate(None)))

    def test_none_nullable_pasa(self):
        field = _make_field(str, nullable=True)
        self.assertEqual(field.validate(None), [])

    def test_null_detiene_validaciones_posteriores(self):
        """Con value=None no se evalúa max_length ni ninguna otra regla."""
        field = _make_field(str, nullable=False, max_length=5)
        codes = _codes(field.validate(None))
        self.assertIn(ValidationCode.NULL_NOT_ALLOWED, codes)
        self.assertNotIn(ValidationCode.MAX_LENGTH, codes)


# ══════════════════════════════════════════════════════════════════════════════
# Field – validación de tipo de dato
# ══════════════════════════════════════════════════════════════════════════════

class TestFieldTipo(unittest.TestCase):
    """Verifica que el chequeo de tipo sea correcto y preciso."""

    def test_tipo_correcto_str_pasa(self):
        self.assertEqual(_make_field(str).validate("hola"), [])

    def test_tipo_correcto_int_pasa(self):
        self.assertEqual(_make_field(int).validate(42), [])

    def test_tipo_correcto_float_pasa(self):
        self.assertEqual(_make_field(float).validate(3.14), [])

    def test_tipo_correcto_bool_pasa(self):
        self.assertEqual(_make_field(bool).validate(True), [])

    def test_tipo_incorrecto_levanta_invalid_type(self):
        errors = _make_field(str).validate(123)
        self.assertIn(ValidationCode.INVALID_TYPE, _codes(errors))

    def test_bool_rechazado_cuando_se_espera_int(self):
        """
        bool es subclase de int en Python. El validador debe rechazarlo
        explícitamente para evitar falsos positivos (True == 1, False == 0).
        """
        errors = _make_field(int).validate(True)
        self.assertIn(ValidationCode.INVALID_TYPE, _codes(errors))

    def test_error_de_tipo_detiene_validaciones_de_string(self):
        """Tras INVALID_TYPE no se evalúa max_length."""
        field = _make_field(str, max_length=3)
        codes = _codes(field.validate(99999))
        self.assertIn(ValidationCode.INVALID_TYPE, codes)
        self.assertNotIn(ValidationCode.MAX_LENGTH, codes)

    def test_sin_field_type_acepta_cualquier_valor(self):
        """field_type=None desactiva el chequeo de tipo."""
        field = _make_field()
        self.assertEqual(field.validate("texto"), [])
        self.assertEqual(field.validate(42),      [])
        self.assertEqual(field.validate([1, 2]),  [])


# ══════════════════════════════════════════════════════════════════════════════
# Field – validaciones de string
# ══════════════════════════════════════════════════════════════════════════════

class TestFieldStrings(unittest.TestCase):
    """Cubre max_length, min_length, is_email e is_uuid."""

    # ── max_length ────────────────────────────────────────────────────────────

    def test_max_length_dentro_del_limite_pasa(self):
        self.assertEqual(_make_field(str, max_length=10).validate("hola"), [])

    def test_max_length_exactamente_en_el_limite_pasa(self):
        self.assertEqual(_make_field(str, max_length=4).validate("hola"), [])

    def test_max_length_superado_levanta_error(self):
        errors = _make_field(str, max_length=3).validate("hola")
        self.assertIn(ValidationCode.MAX_LENGTH, _codes(errors))

    # ── min_length ────────────────────────────────────────────────────────────

    def test_min_length_superado_pasa(self):
        self.assertEqual(_make_field(str, min_length=2).validate("hola"), [])

    def test_min_length_exactamente_en_el_limite_pasa(self):
        self.assertEqual(_make_field(str, min_length=4).validate("hola"), [])

    def test_min_length_no_alcanzado_levanta_error(self):
        errors = _make_field(str, min_length=10).validate("hola")
        self.assertIn(ValidationCode.MIN_LENGTH, _codes(errors))

    def test_string_vacio_con_min_length_1_levanta_error(self):
        """Cadena vacía presente en el body no es 'campo faltante'; min_length la captura."""
        errors = _make_field(str, min_length=1).validate("")
        self.assertIn(ValidationCode.MIN_LENGTH, _codes(errors))

    # ── is_email ──────────────────────────────────────────────────────────────

    def test_email_valido_pasa(self):
        self.assertEqual(_make_field(str, is_email=True).validate("user@example.com"), [])

    def test_email_con_subdominio_pasa(self):
        self.assertEqual(_make_field(str, is_email=True).validate("user@mail.company.co"), [])

    def test_email_sin_arroba_levanta_error(self):
        errors = _make_field(str, is_email=True).validate("userdomain.com")
        self.assertIn(ValidationCode.INVALID_EMAIL, _codes(errors))

    def test_email_sin_dominio_levanta_error(self):
        errors = _make_field(str, is_email=True).validate("user@")
        self.assertIn(ValidationCode.INVALID_EMAIL, _codes(errors))

    def test_email_sin_extension_levanta_error(self):
        errors = _make_field(str, is_email=True).validate("user@domain")
        self.assertIn(ValidationCode.INVALID_EMAIL, _codes(errors))

    def test_cadena_aleatoria_no_es_email(self):
        errors = _make_field(str, is_email=True).validate("not-an-email")
        self.assertIn(ValidationCode.INVALID_EMAIL, _codes(errors))

    # ── is_uuid ───────────────────────────────────────────────────────────────

    def test_uuid_con_guiones_pasa(self):
        self.assertEqual(
            _make_field(str, is_uuid=True).validate("550e8400-e29b-41d4-a716-446655440000"),
            []
        )

    def test_uuid_sin_guiones_pasa(self):
        """Python's uuid.UUID acepta 32 dígitos hex sin guiones."""
        self.assertEqual(
            _make_field(str, is_uuid=True).validate("550e8400e29b41d4a716446655440000"),
            []
        )

    def test_string_aleatorio_no_es_uuid(self):
        errors = _make_field(str, is_uuid=True).validate("not-a-uuid")
        self.assertIn(ValidationCode.INVALID_UUID, _codes(errors))

    def test_uuid_con_caracteres_invalidos_levanta_error(self):
        errors = _make_field(str, is_uuid=True).validate("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.assertIn(ValidationCode.INVALID_UUID, _codes(errors))

    # ── acumulación de errores ────────────────────────────────────────────────

    def test_max_length_y_email_pueden_fallar_juntos(self):
        """Dos reglas de string independientes se acumulan en la misma lista."""
        field = _make_field(str, max_length=3, is_email=True)
        codes = _codes(field.validate("not-an-email"))
        self.assertIn(ValidationCode.MAX_LENGTH,    codes)
        self.assertIn(ValidationCode.INVALID_EMAIL, codes)

    def test_min_length_y_uuid_pueden_fallar_juntos(self):
        """UUID inválido corto: coerce UUID falla antes de min_length de string."""
        field = _make_field(str, min_length=50, is_uuid=True)
        codes = _codes(field.validate("no-es-uuid"))
        self.assertIn(ValidationCode.INVALID_UUID, codes)


# ══════════════════════════════════════════════════════════════════════════════
# Field – validaciones numéricas
# ══════════════════════════════════════════════════════════════════════════════

class TestFieldNumericos(unittest.TestCase):
    """Cubre max_value y min_value para int y float."""

    def test_int_dentro_del_rango_pasa(self):
        self.assertEqual(_make_field(int, min_value=0, max_value=100).validate(50), [])

    def test_int_en_limite_inferior_pasa(self):
        self.assertEqual(_make_field(int, min_value=0).validate(0), [])

    def test_int_en_limite_superior_pasa(self):
        self.assertEqual(_make_field(int, max_value=100).validate(100), [])

    def test_int_supera_max_value_levanta_error(self):
        errors = _make_field(int, max_value=100).validate(101)
        self.assertIn(ValidationCode.MAX_VALUE, _codes(errors))

    def test_int_bajo_min_value_levanta_error(self):
        errors = _make_field(int, min_value=0).validate(-1)
        self.assertIn(ValidationCode.MIN_VALUE, _codes(errors))

    def test_float_supera_max_value_levanta_error(self):
        errors = _make_field(float, max_value=9.99).validate(10.0)
        self.assertIn(ValidationCode.MAX_VALUE, _codes(errors))

    def test_float_bajo_min_value_levanta_error(self):
        errors = _make_field(float, min_value=0.5).validate(0.1)
        self.assertIn(ValidationCode.MIN_VALUE, _codes(errors))

    def test_rango_inconsistente_acumula_ambos_errores(self):
        """
        Si min_value > max_value (configuración inconsistente), un valor
        intermedio rompe ambas reglas y las dos se reportan.
        """
        field = _make_field(int, min_value=50, max_value=10)
        codes = _codes(field.validate(30))
        self.assertIn(ValidationCode.MAX_VALUE, codes)
        self.assertIn(ValidationCode.MIN_VALUE, codes)

    def test_bool_no_pasa_validacion_numerica(self):
        """
        bool hereda de int; el validador lo rechaza como INVALID_TYPE antes
        de evaluar reglas numéricas.
        """
        field = _make_field(int, min_value=0, max_value=100)
        codes = _codes(field.validate(True))
        self.assertIn(ValidationCode.INVALID_TYPE, codes)
        self.assertNotIn(ValidationCode.MAX_VALUE, codes)
        self.assertNotIn(ValidationCode.MIN_VALUE, codes)


# ══════════════════════════════════════════════════════════════════════════════
# RequestBody – campos requeridos
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestBodyRequeridos(unittest.TestCase):
    """Verifica la detección de campos obligatorios ausentes."""

    class _Body(RequestBody):
        nombre = Field(str, max_length=100, pattern=PATTERN_TEXT, required=True)
        edad   = Field(int, required=True)

    def test_todos_los_requeridos_presentes_pasa(self):
        body = self._Body({"nombre": "Ana", "edad": 30})
        is_valid, errors = body.validate()
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_campo_requerido_ausente_levanta_required(self):
        body = self._Body({"nombre": "Ana"})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn("edad", _fields_with_error(errors))
        self.assertIn(ValidationCode.REQUIRED, _codes(errors))

    def test_todos_los_requeridos_ausentes_todos_reportados(self):
        body = self._Body({})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        campos = _fields_with_error(errors)
        self.assertIn("nombre", campos)
        self.assertIn("edad",   campos)

    def test_valor_cero_no_es_campo_ausente(self):
        """El valor 0 es un valor válido, no ausencia del campo."""
        class Body(RequestBody):
            stock = Field(int, required=True, min_value=0)
        body = Body({"stock": 0})
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)

    def test_cadena_vacia_no_es_campo_ausente(self):
        """
        Una cadena vacía está presente en el body; REQUIRED no aplica.
        min_length la captura si corresponde.
        """
        class Body(RequestBody):
            nombre = Field(str, max_length=100, pattern=PATTERN_TEXT, required=True, min_length=1)
        body = Body({"nombre": ""})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        codes = _codes(errors)
        self.assertIn(ValidationCode.MIN_LENGTH, codes)
        self.assertNotIn(ValidationCode.REQUIRED, codes)

    def test_false_no_es_campo_ausente(self):
        """El valor False es un valor válido para un campo bool."""
        class Body(RequestBody):
            activo = Field(bool, required=True)
        body = Body({"activo": False})
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)


# ══════════════════════════════════════════════════════════════════════════════
# RequestBody – campos opcionales
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestBodyOpcionales(unittest.TestCase):
    """Verifica el comportamiento de campos con required=False."""

    class _Body(RequestBody):
        nombre = Field(str, max_length=100, pattern=PATTERN_TEXT, required=True)
        bio    = Field(str, required=False, nullable=True, max_length=200, pattern=PATTERN_TEXT)

    def test_campo_opcional_ausente_pasa(self):
        body = self._Body({"nombre": "Ana"})
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)

    def test_campo_opcional_presente_y_valido_pasa(self):
        body = self._Body({"nombre": "Ana", "bio": "Desarrolladora senior."})
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)

    def test_campo_opcional_nullable_con_null_pasa(self):
        body = self._Body({"nombre": "Ana", "bio": None})
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)

    def test_campo_opcional_presente_pero_invalido_levanta_error(self):
        body = self._Body({"nombre": "Ana", "bio": "x" * 201})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn(ValidationCode.MAX_LENGTH, _codes(errors))

    def test_campo_opcional_no_nullable_con_null_levanta_error(self):
        class Body(RequestBody):
            tag = Field(str, max_length=64, pattern=PATTERN_TEXT, required=False, nullable=False)
        body = Body({"tag": None})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn(ValidationCode.NULL_NOT_ALLOWED, _codes(errors))


# ══════════════════════════════════════════════════════════════════════════════
# RequestBody – validate() integración completa
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestBodyValidate(unittest.TestCase):
    """
    Prueba el flujo completo de validate() con un body realista
    que combina múltiples tipos de reglas y campos.
    """

    class _ProductBody(RequestBody):
        nombre     = Field(str, min_length=2, max_length=100, pattern=PATTERN_TEXT)
        email      = Field(str, is_email=True)
        empresa_id = Field(str, is_uuid=True)
        stock      = Field(int, min_value=0)
        descripcion = Field(
            str, required=False, nullable=True, max_length=500, pattern=PATTERN_TEXT,
        )

    def _datos_validos(self, **overrides) -> dict:
        base = {
            "nombre":     "Producto Alpha",
            "email":      "vendedor@empresa.com",
            "empresa_id": "550e8400-e29b-41d4-a716-446655440000",
            "stock":      10,
        }
        base.update(overrides)
        return base

    def test_body_valido_completo_pasa(self):
        body = self._ProductBody(self._datos_validos())
        is_valid, errors = body.validate()
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_body_valido_con_opcional_pasa(self):
        data = self._datos_validos(descripcion="Producto de alta calidad.")
        body = self._ProductBody(data)
        is_valid, _ = body.validate()
        self.assertTrue(is_valid)

    def test_multiples_campos_invalidos_todos_reportados(self):
        body = self._ProductBody({
            "nombre":     "x",       # demasiado corto
            "email":      "bad",     # email inválido
            "empresa_id": "abc",     # uuid inválido
            "stock":      -5,        # negativo
        })
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        campos = _fields_with_error(errors)
        self.assertIn("nombre",     campos)
        self.assertIn("email",      campos)
        self.assertIn("empresa_id", campos)
        self.assertIn("stock",      campos)

    def test_solo_campo_invalido_reporta_unicamente_ese(self):
        body = self._ProductBody(self._datos_validos(stock=-1))
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "stock")

    def test_propiedad_data_devuelve_dict_original(self):
        data = self._datos_validos()
        body = self._ProductBody(data)
        self.assertEqual(body.data, data)

    def test_data_no_dict_tratado_como_body_vacio(self):
        """Si request.data llega como string/lista, se trata como dict vacío."""
        body = self._ProductBody("datos incorrectos")
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        # Todos los campos requeridos deben aparecer como REQUIRED
        self.assertEqual(len(errors), 4)
        codes = _codes(errors)
        self.assertTrue(all(c == ValidationCode.REQUIRED for c in codes))

    def test_campos_extra_en_body_son_rechazados(self):
        """Claves no declaradas en el body producen UNKNOWN_FIELD."""
        data = self._datos_validos()
        data["campo_no_declarado"] = "valor inesperado"
        body = self._ProductBody(data)
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn(ValidationCode.UNKNOWN_FIELD, _codes(errors))


# ══════════════════════════════════════════════════════════════════════════════
# RequestBody – herencia de campos
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestBodyHerencia(unittest.TestCase):
    """
    Verifica que los campos declarados en clases padre se hereden
    correctamente en clases hijas.
    """

    class _BaseBody(RequestBody):
        nombre = Field(str, max_length=100, pattern=PATTERN_TEXT, required=True, min_length=2)

    class _ChildBody(_BaseBody):
        email = Field(str, is_email=True)

    def test_hijo_hereda_campos_del_padre(self):
        body = self._ChildBody({"nombre": "Ana", "email": "ana@mail.com"})
        is_valid, errors = body.validate()
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_hijo_valida_campo_heredado(self):
        """El campo 'nombre' definido en el padre sigue siendo validado."""
        body = self._ChildBody({"nombre": "x", "email": "ana@mail.com"})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn("nombre", _fields_with_error(errors))

    def test_campo_requerido_heredado_ausente_levanta_required(self):
        body = self._ChildBody({"email": "ana@mail.com"})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn("nombre", _fields_with_error(errors))

    def test_campo_hijo_invalido_reportado(self):
        body = self._ChildBody({"nombre": "Ana", "email": "no-es-email"})
        is_valid, errors = body.validate()
        self.assertFalse(is_valid)
        self.assertIn("email", _fields_with_error(errors))


# ══════════════════════════════════════════════════════════════════════════════
# RequestBody – error_response()
# ══════════════════════════════════════════════════════════════════════════════

class TestRequestBodyErrorResponse(unittest.TestCase):
    """Verifica la estructura de la respuesta HTTP 400 generada por error_response()."""

    def setUp(self):
        class Body(RequestBody):
            email = Field(str, is_email=True)

        self.body = Body({"email": "invalido"})
        _, self.errors = self.body.validate()

    def test_status_code_http_es_400(self):
        response = self.body.error_response(self.errors)
        self.assertEqual(response.status_code, 400)

    def test_body_contiene_claves_estandar(self):
        response = self.body.error_response(self.errors)
        data = response.data
        self.assertIn("status_code", data)
        self.assertIn("message",     data)
        self.assertIn("resolved_at", data)
        self.assertIn("errors",      data)

    def test_status_code_en_body_es_400(self):
        response = self.body.error_response(self.errors)
        self.assertEqual(response.data["status_code"], 400)

    def test_errors_es_lista(self):
        response = self.body.error_response(self.errors)
        self.assertIsInstance(response.data["errors"], list)

    def test_cada_error_contiene_field_code_detail(self):
        response = self.body.error_response(self.errors)
        for item in response.data["errors"]:
            self.assertIn("field",  item)
            self.assertIn("code",   item)
            self.assertIn("detail", item)

    def test_error_response_con_lista_vacia_retorna_400(self):
        """Aunque no haya errores, error_response sigue retornando 400."""
        response = self.body.error_response([])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"], [])

    def test_multiples_errores_todos_incluidos_en_response(self):
        class Body(RequestBody):
            nombre = Field(str, max_length=100, pattern=PATTERN_TEXT, required=True)
            email  = Field(str, is_email=True)
            uuid   = Field(str, is_uuid=True)

        body = Body({"email": "bad", "uuid": "bad"})  # nombre ausente
        _, errors = body.validate()
        response = body.error_response(errors)
        self.assertEqual(len(response.data["errors"]), 3)


if __name__ == "__main__":
    unittest.main()
