try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


def stats_available():
    return _PSUTIL_AVAILABLE


def system_ram_percent():
    return psutil.virtual_memory().percent


def system_swap_percent():
    return psutil.swap_memory().percent


def _system_ram_swap_total_bytes():
    # denominador para normalizar el peso de un proceso: RAM+swap totales
    # de la maquina, no solo RAM. Un proceso que este parcialmente
    # swappeado sigue "pesando" lo mismo en terminos de recursos usados,
    # aunque una parte de esa memoria ya no este en RAM.
    return psutil.virtual_memory().total + psutil.swap_memory().total


class ProcessTreeMemory:
    """Calcula el % de RAM+swap combinado (0-100 sobre el total del
    sistema) que usa un proceso y todos sus hijos, sumados.

    A diferencia del CPU, la memoria no cae a 0% en cuanto el proceso
    queda inactivo: un programa que dejo de usar CPU pero sigue corriendo
    sigue reteniendo la memoria que tiene reservada, asi que este numero
    da una lectura mas estable de "cuanto pesa" cada ventana que el % de
    CPU (que fluctua a 0% todo el tiempo para cualquier app idle).

    Un proceso "hijo" cubre, por ejemplo, un compilador lanzado desde una
    terminal, o un proceso de decodificacion de video lanzado por un
    navegador: sin sumar el arbol completo, ese consumo no se reflejaria
    en el PID de la ventana en si.

    A diferencia de ProcessTreeCpu (que necesitaba mantener la misma
    instancia de psutil.Process entre polls para medir un intervalo), la
    memoria es una lectura instantanea: no hace falta "primeria" nada
    entre polls, cada llamada a poll() puede re-descubrir el arbol de
    procesos entero sin perder precision.
    """

    def __init__(self, root_pid):
        self._root_pid = root_pid

    def _discover(self):
        if not self._root_pid:
            return []
        try:
            root = psutil.Process(self._root_pid)
        except psutil.NoSuchProcess:
            return []
        procs = [root]
        try:
            procs.extend(root.children(recursive=True))
        except psutil.NoSuchProcess:
            pass
        return procs

    def poll(self):
        total_bytes = 0
        for p in self._discover():
            try:
                total_bytes += p.memory_info().rss
                try:
                    # memory_full_info() suma tambien la porcion swappeada
                    # (campo "swap", solo disponible en Linux); no todos
                    # los procesos son legibles (AccessDenied en procesos
                    # de otro usuario), en ese caso se cuenta solo el RSS.
                    total_bytes += getattr(p.memory_full_info(), "swap", 0)
                except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        denom = _system_ram_swap_total_bytes()
        if denom <= 0:
            return 0.0
        return (total_bytes / denom) * 100
