from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cart import CartRepository
from app.repositories.specs.cart import CartSpec
from app.schemas.api.responses import CartItemResponse, CartResponse


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CartRepository(session)

    async def change_cart_item_quantity(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
    ):
        cart = await self.repo.get_cart(CartSpec(user_id=user_id))

        if quantity <= 0:
            await self.repo.delete_cart_item(
                cart_id=cart.id,
                product_id=product_id,
            )

            await self.session.commit()
            return

        cart_item = await self.repo.upsert_cart_item(
            cart_id=cart.id,
            product_id=product_id,
            quantity=quantity,
        )

        await self.session.commit()

        return cart_item

    async def get_cart(self, user_id: int) -> CartResponse:
        cart = await self.repo.get_cart(
            CartSpec(user_id=user_id, include_items=True)
        )
        return CartResponse(
            items=[
                CartItemResponse(
                    product_id=str(item.product_id),
                    quantity=item.quantity,
                )
                for item in cart.items
            ]
        )
