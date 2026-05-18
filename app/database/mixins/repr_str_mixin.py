from sqlalchemy import inspect


class ReprStrMixin:
    HIDDEN_FIELDS = {"password_hash"}

    def _format(self) -> str:
        try:
            mapper = inspect(self.__class__)
            columns = mapper.columns
        except Exception:
            return f"{self.__class__.__name__}"

        pk_fields = []
        fk_fields = []
        other_fields = []

        for col in columns:
            name = col.key

            if name in getattr(self, "HIDDEN_FIELDS", set()):
                continue

            value = getattr(self, name)

            # форматирование строк
            if isinstance(value, str):
                value = f'"{value}"'

            # определяем PK
            is_pk = col.primary_key

            # определяем FK
            is_fk = len(col.foreign_keys) > 0

            field = (name, value, is_pk, is_fk)

            if is_pk:
                pk_fields.append(field)
            elif is_fk:
                fk_fields.append(field)
            else:
                other_fields.append(field)

        # алфавит внутри групп
        pk_fields.sort(key=lambda x: x[0])
        fk_fields.sort(key=lambda x: x[0])
        other_fields.sort(key=lambda x: x[0])

        def format_field(f):
            name, value, is_pk, is_fk = f

            tags = []
            if is_pk:
                tags.append("PK")
            if is_fk:
                tags.append("FK")

            tag_str = f" [{'|'.join(tags)}]" if tags else ""

            return f"{name}={value}{tag_str}"

        parts = (
            [format_field(f) for f in pk_fields]
            + [format_field(f) for f in fk_fields]
            + [format_field(f) for f in other_fields]
        )

        return f"<{self.__class__.__name__}: " + ", ".join(parts) + ">"

    def __repr__(self) -> str:
        return self._format()

    def __str__(self) -> str:
        return self._format()
