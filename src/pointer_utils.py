"""
Utilities for handling pointers in ROM files.

Provides functions for reading, writing, and updating pointer tables.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PointerInfo:
    """Information about a pointer in the ROM."""

    address: int
    target_address: int
    format_type: str
    size_bytes: int


class PointerUtils:
    """Utility functions for pointer manipulation."""

    @staticmethod
    def read_16bit_pointer(
        rom_data: bytes, address: int, little_endian: bool = True
    ) -> int:
        """Read a 16-bit pointer from ROM data.

        Args:
            rom_data: ROM file data
            address: Address of the pointer
            little_endian: Whether pointer is little endian

        Returns:
            Target address pointed to
        """
        if address + 1 >= len(rom_data):
            raise ValueError(f"Pointer address 0x{address:04X} is beyond ROM size")

        if little_endian:
            low = rom_data[address]
            high = rom_data[address + 1]
            return (high << 8) | low
        else:
            high = rom_data[address]
            low = rom_data[address + 1]
            return (high << 8) | low

    @staticmethod
    def write_16bit_pointer(
        rom_data: bytearray, address: int, target: int, little_endian: bool = True
    ) -> None:
        """Write a 16-bit pointer to ROM data.

        Args:
            rom_data: ROM file data (mutable)
            address: Address to write pointer at
            target: Target address to point to
            little_endian: Whether pointer is little endian
        """
        if address + 1 >= len(rom_data):
            raise ValueError(f"Pointer address 0x{address:04X} is beyond ROM size")

        if target > 0xFFFF:
            raise ValueError(
                f"Target address 0x{target:04X} too large for 16-bit pointer"
            )

        high = (target >> 8) & 0xFF
        low = target & 0xFF

        if little_endian:
            rom_data[address] = low
            rom_data[address + 1] = high
        else:
            rom_data[address] = high
            rom_data[address + 1] = low

    @staticmethod
    def read_pointer_table(
        rom_data: bytes,
        table_address: int,
        count: int,
        format_type: str = "little_endian_16bit",
        base_offset: int = 0,
    ) -> List[PointerInfo]:
        """Read an entire pointer table.

        Args:
            rom_data: ROM file data
            table_address: Starting address of pointer table
            count: Number of pointers in table
            format_type: Format of pointers
            base_offset: Offset to add to each pointer value

        Returns:
            List of pointer information
        """
        pointers = []

        if format_type == "little_endian_16bit":
            little_endian = True
            pointer_size = 2
        elif format_type == "big_endian_16bit":
            little_endian = False
            pointer_size = 2
        else:
            raise ValueError(f"Unsupported pointer format: {format_type}")

        for i in range(count):
            ptr_address = table_address + (i * pointer_size)
            target = PointerUtils.read_16bit_pointer(
                rom_data, ptr_address, little_endian
            )
            target += base_offset

            pointers.append(
                PointerInfo(
                    address=ptr_address,
                    target_address=target,
                    format_type=format_type,
                    size_bytes=pointer_size,
                )
            )

        return pointers

    @staticmethod
    def update_pointer_table(
        rom_data: bytearray,
        pointers: List[PointerInfo],
        address_changes: Dict[int, int],
    ) -> None:
        """Update pointer table with new addresses.

        Args:
            rom_data: ROM file data (mutable)
            pointers: List of pointers to update
            address_changes: Mapping of old address -> new address
        """
        for pointer in pointers:
            old_target = pointer.target_address
            if old_target in address_changes:
                new_target = address_changes[old_target]

                if pointer.format_type in ["little_endian_16bit", "big_endian_16bit"]:
                    little_endian = pointer.format_type == "little_endian_16bit"
                    PointerUtils.write_16bit_pointer(
                        rom_data, pointer.address, new_target, little_endian
                    )

    @staticmethod
    def find_pointer_references(
        rom_data: bytes,
        target_address: int,
        search_range: Optional[Tuple[int, int]] = None,
    ) -> List[int]:
        """Find all pointers that reference a specific address.

        Args:
            rom_data: ROM file data
            target_address: Address to search for
            search_range: Optional (start, end) range to search within

        Returns:
            List of addresses that contain pointers to target_address
        """
        references = []
        start, end = search_range or (0, len(rom_data) - 1)

        # Convert target to bytes (little endian 16-bit)
        target_low = target_address & 0xFF
        target_high = (target_address >> 8) & 0xFF

        # Search for little endian pointers
        for i in range(start, min(end, len(rom_data) - 1)):
            if rom_data[i] == target_low and rom_data[i + 1] == target_high:
                references.append(i)

        # Search for big endian pointers
        for i in range(start, min(end, len(rom_data) - 1)):
            if rom_data[i] == target_high and rom_data[i + 1] == target_low:
                references.append(i)

        return references

    @staticmethod
    def calculate_bank_address(
        address: int, bank_size: int = 0x4000, bank_offset: int = 0x8000
    ) -> Tuple[int, int]:
        """Calculate bank number and offset for banked memory systems.

        Args:
            address: Absolute address
            bank_size: Size of each bank
            bank_offset: Starting offset for banked region

        Returns:
            Tuple of (bank_number, offset_in_bank)
        """
        if address < bank_offset:
            # Address is in fixed region
            return 0, address

        banked_address = address - bank_offset
        bank_number = banked_address // bank_size
        offset_in_bank = banked_address % bank_size

        return bank_number, offset_in_bank + bank_offset

    @staticmethod
    def validate_pointer_chain(
        rom_data: bytes, pointers: List[PointerInfo]
    ) -> List[str]:
        """Validate a chain of pointers for consistency.

        Args:
            rom_data: ROM file data
            pointers: List of pointers to validate

        Returns:
            List of validation warnings/errors
        """
        issues = []

        for i, pointer in enumerate(pointers):
            # Check if pointer address is valid
            if pointer.address >= len(rom_data):
                issues.append(
                    f"Pointer {i}: address 0x{pointer.address:04X} beyond ROM"
                )
                continue

            # Check if target address is valid
            if pointer.target_address >= len(rom_data):
                issues.append(
                    f"Pointer {i}: target 0x{pointer.target_address:04X} beyond ROM"
                )
                continue

            # Check for null pointers
            if pointer.target_address == 0:
                issues.append(f"Pointer {i}: null pointer at 0x{pointer.address:04X}")

            # Check for obviously invalid targets (pointing to header, etc.)
            if pointer.target_address < 0x100:
                issues.append(
                    f"Pointer {i}: suspicious target 0x{pointer.target_address:04X}"
                )

        # Check for duplicate targets
        targets = [p.target_address for p in pointers]
        duplicate_targets = set([t for t in targets if targets.count(t) > 1])
        for target in duplicate_targets:
            issues.append(f"Multiple pointers target address 0x{target:04X}")

        return issues

    @staticmethod
    def compact_pointer_targets(
        rom_data: bytearray, pointers: List[PointerInfo], strings_data: List[bytes]
    ) -> Dict[int, int]:
        """Compact string data and return address mapping.

        Args:
            rom_data: ROM file data (mutable)
            pointers: List of pointers that reference strings
            strings_data: New string data to insert

        Returns:
            Dictionary mapping old addresses to new addresses
        """
        if len(pointers) != len(strings_data):
            raise ValueError("Number of pointers must match number of strings")

        address_changes = {}
        current_address = min(p.target_address for p in pointers)

        # Sort pointers by target address to maintain order
        sorted_pointers = sorted(pointers, key=lambda p: p.target_address)

        for i, pointer in enumerate(sorted_pointers):
            old_address = pointer.target_address
            new_data = strings_data[i]

            # Update mapping
            address_changes[old_address] = current_address

            # Write new data
            end_address = current_address + len(new_data)
            if end_address > len(rom_data):
                raise ValueError(
                    f"Not enough space to insert string at 0x{current_address:04X}"
                )

            rom_data[current_address:end_address] = new_data
            current_address = end_address

        return address_changes
