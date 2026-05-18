from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
from .specs.cart import CartSpec
from app.models import CartItem, Cart, Product


class CartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cart(self, spec: CartSpec):
        stmt = select(Cart).where(Cart.user_id == spec.user_id)
        if spec.include_items:
            items_loader = selectinload(Cart.items)
            if spec.include_product_details:
                items_loader = items_loader.selectinload(
                    CartItem.product
                ).selectinload(Product.images)
            stmt = stmt.options(items_loader)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_cart(self, cart_id: int) -> None:
        stmt = delete(CartItem).where(CartItem.cart_id == cart_id)
        await self.session.execute(stmt)

    async def get_cart_item(self, cart_id: int, product_id: int):
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_cart_item(
        self,
        cart_id: int,
        product_id: int,
        quantity: int,
    ):
        stmt = insert(CartItem).values(
            cart_id=cart_id,
            product_id=product_id,
            quantity=quantity,
        )

        stmt = stmt.on_conflict_do_update(
            constraint="uq_cart_product",
            set_={
                "quantity": quantity,
            },
        ).returning(CartItem)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_cart_item(
        self,
        cart_id: int,
        product_id: int,
    ):
        stmt = delete(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )

        await self.session.execute(stmt)
