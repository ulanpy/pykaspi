from __future__ import annotations

import argparse
import asyncio
from getpass import getpass
from pathlib import Path

from .client import KaspiClient
from .device import DeviceIdentity
from .exceptions import KaspiApiError, KaspiReauthRequiredError, PykaspiError
from .terminal import KaspiTerminal
from .validation import normalize_phone


async def prepare_terminal(path: Path, phone: str) -> KaspiTerminal:
    terminal = KaspiTerminal.load(path) if path.exists() else None
    device = terminal.device if terminal is not None else DeviceIdentity.generate()

    if terminal is not None:
        async with terminal.client() as client:
            try:
                if (await client.session.check(terminal.session)).active:
                    return terminal
            except KaspiApiError as error:
                if error.status_code not in (401, 403):
                    raise
            try:
                terminal.session = await client.auth.refresh(terminal.session)
                terminal.save(path)
                return terminal
            except KaspiReauthRequiredError:
                pass

    async with KaspiClient(device=device) as client:
        init = await client.auth.init()
        step = await client.auth.send_phone(init.process_id, phone)
        if step.requires_password:
            step = await client.auth.submit_password(
                init.process_id,
                getpass("Пароль Kaspi Pay (вводится только локально): "),
            )
        if step.requires_otp:
            session = await client.auth.verify_otp(
                init.process_id,
                getpass("Код из SMS (вводится только локально): "),
            )
        elif step.requires_mobile_confirmation:
            input("Подтвердите вход в Kaspi Pay и нажмите Enter: ")
            session = await client.auth.confirm_mobile(init.process_id)
        else:
            raise RuntimeError(
                f"Kaspi запросил неподдерживаемый этап входа: {step.view}, {step.challenge_type}"
            )
    terminal = KaspiTerminal(device=device, session=session)
    terminal.save(path)
    return terminal


async def _main(args: argparse.Namespace) -> None:
    terminal = await prepare_terminal(args.state, normalize_phone(args.phone))
    print(f"Терминал готов: {terminal.session.org_name or 'Kaspi Pay'}")
    print(f"Файл: {args.state}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Создать или обновить один JSON-файл терминала Kaspi Pay."
    )
    parser.add_argument("--state", type=Path, required=True, help="Путь к terminal.json")
    parser.add_argument("--phone", required=True, help="Номер кассира Kaspi Pay")
    args = parser.parse_args()
    try:
        asyncio.run(_main(args))
    except (PykaspiError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Ошибка: {error}\n")


if __name__ == "__main__":
    main()
